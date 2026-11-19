using System.Runtime.CompilerServices;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;
using Microsoft.Extensions.Logging;
using Microsoft.VisualStudio.TestTools.UnitTesting;
using OneNexus.Observability.Rules;

namespace OneNexus.Observability.Tests;

[TestClass]
public sealed class DegradationTests
{
    private static readonly Dictionary<string, LogLevel> Levels = new()
    {
        ["TRACE"] = LogLevel.Trace, ["DEBUG"] = LogLevel.Debug, ["INFO"] = LogLevel.Information,
        ["WARN"] = LogLevel.Warning, ["ERROR"] = LogLevel.Error, ["FATAL"] = LogLevel.Critical,
    };

    // Writes are asynchronous (write model F2): drain the provider before reading its output.
    private static string[] Lines(JsonLogProvider provider, StringWriter writer)
    {
        Assert.IsTrue(provider.CloseWithin(TimeSpan.FromSeconds(10)));
        return writer.ToString().Split('\n', StringSplitOptions.RemoveEmptyEntries);
    }
    private static int Bytes(string text) => Encoding.UTF8.GetByteCount(text);

    private static string Expand(JsonElement value) => value.ValueKind == JsonValueKind.String
        ? value.GetString()!
        : string.Concat(Enumerable.Repeat(value.GetProperty("repeat").GetString()!, value.GetProperty("count").GetInt32()));

    private static List<KeyValuePair<string, object?>> Fields(JsonElement fields) =>
        fields.EnumerateObject().Select(p => new KeyValuePair<string, object?>(p.Name, Expand(p.Value))).ToList();

    [MethodImpl(MethodImplOptions.NoInlining)]
    private static void RaiseNested(string message, int depth)
    {
        if (depth <= 0) throw new InvalidOperationException(message);
        RaiseNested(message, depth - 1);
    }

    private static Exception Caught(string message, int depth)
    {
        try { RaiseNested(message, depth); }
        catch (InvalidOperationException ex) { return ex; }
        throw new AssertFailedException("not_thrown");
    }

    [TestMethod]
    public void SharedDegradationScenarios()
    {
        using var suite = JsonDocument.Parse(File.ReadAllBytes(Environment.GetEnvironmentVariable("ONENEXUS_LOGGING_SCENARIOS")!));
        var root = suite.RootElement;
        var allowed = root.GetProperty("degradation_allowed_fields").EnumerateArray().Select(f => f.GetString()!).ToArray();
        var errorType = root.GetProperty("degradation_error_type").GetProperty("dotnet").GetString();
        var cases = root.GetProperty("degradation_cases");
        Assert.IsTrue(cases.GetArrayLength() > 0);
        foreach (var item in cases.EnumerateArray())
        {
            var id = item.GetProperty("id").GetString();
            using var output = new StringWriter();
            using var provider = new JsonLogProvider(new("shared-test", "development", "region-1", allowed), output);
            var logger = provider.CreateLogger("degradation");
            var message = Expand(item.GetProperty("message"));
            var fields = Fields(item.GetProperty("fields"));
            var level = Levels[item.GetProperty("level").GetString()!];
            if (item.TryGetProperty("error", out var error))
            {
                var exception = Caught(error.GetProperty("message").GetString()!, error.GetProperty("nested_calls").GetInt32());
                logger.Log(level, default, fields, exception, (_, _) => message);
            }
            else logger.Log(level, default, fields, null, (_, _) => message);
            Assert.AreEqual(0L, provider.DroppedRecords, id);
            var line = Lines(provider, output).Single();
            var row = JsonDocument.Parse(line).RootElement;
            Assert.IsEmpty(Contract.Validate(row), id);
            var expect = item.GetProperty("expect");

            var truncated = expect.GetProperty("truncated");
            if (truncated.ValueKind == JsonValueKind.Null) Assert.IsFalse(row.TryGetProperty("logging.truncated", out _), id);
            else Assert.AreEqual(truncated.GetBoolean(), row.GetProperty("logging.truncated").GetBoolean(), id);
            var dropped = expect.GetProperty("dropped_field_count");
            if (dropped.ValueKind == JsonValueKind.Null) Assert.IsFalse(row.TryGetProperty("logging.dropped_field_count", out _), id);
            else Assert.AreEqual(dropped.GetInt32(), row.GetProperty("logging.dropped_field_count").GetInt32(), id);

            var actual = row.GetProperty("message").GetString()!;
            if (expect.TryGetProperty("message", out var exact)) Assert.AreEqual(Expand(exact), actual, id);
            else
            {
                Assert.IsLessThanOrEqualTo(expect.GetProperty("message_max_bytes").GetInt32(), Bytes(actual), id);
                Assert.StartsWith(expect.GetProperty("message_prefix").GetString()!, actual, id);
                Assert.EndsWith(expect.GetProperty("message_suffix").GetString()!, actual, id);
            }
            if (expect.TryGetProperty("fields", out var expected))
                foreach (var (key, value) in Fields(expected)) Assert.AreEqual(value, row.GetProperty(key).GetString(), id);
            if (expect.TryGetProperty("absent", out var absent))
                foreach (var key in absent.EnumerateArray()) Assert.IsFalse(row.TryGetProperty(key.GetString()!, out _), id);
            if (expect.TryGetProperty("field_bounds", out var bounds))
                foreach (var bound in bounds.EnumerateObject())
                {
                    var value = row.GetProperty(bound.Name).GetString()!;
                    Assert.IsLessThanOrEqualTo(bound.Value.GetProperty("max_bytes").GetInt32(), Bytes(value), id);
                    Assert.StartsWith(bound.Value.GetProperty("prefix").GetString()!, value, id);
                    Assert.EndsWith(bound.Value.GetProperty("suffix").GetString()!, value, id);
                }
            if (expect.TryGetProperty("record_max_bytes", out var recordMax))
                Assert.IsLessThanOrEqualTo(recordMax.GetInt32(), Bytes(line), id);
            if (expect.TryGetProperty("error_type", out var hasError) && hasError.GetBoolean())
            {
                Assert.AreEqual(errorType, row.GetProperty("error.type").GetString(), id);
                var stack = row.GetProperty("exception.stacktrace").GetString()!;
                Assert.IsLessThanOrEqualTo(expect.GetProperty("stacktrace_max_bytes").GetInt32(), Bytes(stack), id);
                var pattern = new Regex(expect.GetProperty("stacktrace_line_pattern").GetString()!);
                var frames = stack.Split('\n');
                Assert.IsTrue(frames.All(pattern.IsMatch), id);
                Assert.StartsWith("at OneNexus.Observability.Tests.DegradationTests.RaiseNested (DegradationTests.cs:", frames[0], id);
            }
            if (expect.TryGetProperty("stacktrace_excludes", out var excludes))
                foreach (var marker in excludes.EnumerateArray()) Assert.DoesNotContain(marker.GetString()!, line, id);
        }
    }

    [TestMethod]
    public void CallerSuppliedErrorTypeWins()
    {
        using var output = new StringWriter();
        using var provider = new JsonLogProvider(new("shared-test", "development", "region-1", ["error.type"]), output);
        provider.CreateLogger("test").LogError(Caught("private-detail", 1), "Failed {error.type}", "Payments.Declined");
        var row = JsonDocument.Parse(Lines(provider, output).Single()).RootElement;
        Assert.AreEqual("Payments.Declined", row.GetProperty("error.type").GetString());
        Assert.StartsWith("at OneNexus.Observability.Tests.DegradationTests.RaiseNested", row.GetProperty("exception.stacktrace").GetString()!);
        Assert.IsFalse(row.TryGetProperty("logging.truncated", out _));
        Assert.DoesNotContain("private", output.ToString());
    }

    [TestMethod]
    public void UnsupportedFieldValuesAreRemovedAndCountedNotTheRecord()
    {
        using var output = new StringWriter();
        using var provider = new JsonLogProvider(new("shared-test", "development", "region-1", ["example.a", "example.b", "example.c", "example.d", "example.o", "example.kept"]), output);
        var fields = new Dictionary<string, object?>
        {
            ["example.a"] = double.NaN, ["example.b"] = float.PositiveInfinity, ["example.c"] = typeof(string), // Not serialisable.
            ["example.d"] = "x\uD800y", // Lone surrogate: not valid Unicode.
            ["example.o"] = new Dictionary<string, object?> { ["n"] = 1 }, // Not a flat scalar (field registry E1).
            ["example.kept"] = 1,
        };
        provider.CreateLogger("test").Log(LogLevel.Information, default, fields, null, (_, _) => "Unsupported values");
        Assert.AreEqual(0L, provider.DroppedRecords);
        var row = JsonDocument.Parse(Lines(provider, output).Single()).RootElement;
        Assert.AreEqual(5, row.GetProperty("logging.dropped_field_count").GetInt32());
        Assert.IsTrue(new[] { "example.a", "example.b", "example.c", "example.d", "example.o" }.All(k => !row.TryGetProperty(k, out _)));
        Assert.AreEqual(1, row.GetProperty("example.kept").GetInt32());
        Assert.IsEmpty(Contract.Validate(row));
    }

    [TestMethod]
    public void InvalidCallerErrorFieldsAreRemovedAndTheSdkValuesApply()
    {
        using var output = new StringWriter();
        using var provider = new JsonLogProvider(new("shared-test", "development", "region-1", ["error.type", "exception.stacktrace"]), output);
        var fields = new Dictionary<string, object?> { ["error.type"] = new string('e', Contract.MaxErrorTypeChars + 1), ["exception.stacktrace"] = 42 };
        provider.CreateLogger("test").Log(LogLevel.Error, default, fields, Caught("private", 1), (_, _) => "Failed");
        var row = JsonDocument.Parse(Lines(provider, output).Single()).RootElement;
        Assert.AreEqual(2, row.GetProperty("logging.dropped_field_count").GetInt32());
        Assert.AreEqual("System.InvalidOperationException", row.GetProperty("error.type").GetString());
        Assert.StartsWith("at OneNexus.Observability.Tests.DegradationTests.RaiseNested", row.GetProperty("exception.stacktrace").GetString()!);
        Assert.IsEmpty(Contract.Validate(row));
    }

    [TestMethod]
    public void CallerStackSuppressesTheSdkStackCutFlag()
    {
        using var output = new StringWriter();
        using var provider = new JsonLogProvider(new("shared-test", "development", "region-1", ["exception.stacktrace"]), output);
        var fields = new Dictionary<string, object?> { ["exception.stacktrace"] = "at caller (app.cs:1)" };
        // 60 frames exceed the 2 KiB stack budget, so the SDK stack would be cut; the caller's value wins instead.
        provider.CreateLogger("test").Log(LogLevel.Error, default, fields, Caught("private", 60), (_, _) => "Failed");
        var row = JsonDocument.Parse(Lines(provider, output).Single()).RootElement;
        Assert.AreEqual("at caller (app.cs:1)", row.GetProperty("exception.stacktrace").GetString());
        Assert.AreEqual("System.InvalidOperationException", row.GetProperty("error.type").GetString());
        Assert.IsFalse(row.TryGetProperty("logging.truncated", out _));
    }

    [TestMethod]
    public void DroppedFieldCountIsClampedToTheSchemaMaximum()
    {
        using var output = new StringWriter();
        using var provider = new JsonLogProvider(new("shared-test", "development", "region-1"), output);
        var fields = Enumerable.Range(0, Contract.MaxDroppedFieldCount + 6).Select(i => new KeyValuePair<string, object?>($"unknown.{i}", i)).ToList();
        provider.CreateLogger("test").Log(LogLevel.Information, default, fields, null, (_, _) => "Many fields");
        var row = JsonDocument.Parse(Lines(provider, output).Single()).RootElement;
        Assert.AreEqual(Contract.MaxDroppedFieldCount, row.GetProperty("logging.dropped_field_count").GetInt32());
        Assert.IsEmpty(Contract.Validate(row));
    }

    [TestMethod]
    public void TemplateMetadataIsNotCountedButUnknownTemplateFieldsAre()
    {
        using var output = new StringWriter();
        using var provider = new JsonLogProvider(new("shared-test", "development", "region-1", ["job.attempt"]), output);
        var logger = provider.CreateLogger("test");
        logger.LogInformation("Attempt {job.attempt}", 1);
        logger.LogInformation("Attempt {job.attempt} for {tenant}", 2, "t1");
        var rows = Lines(provider, output).Select(l => JsonDocument.Parse(l).RootElement).ToArray();
        Assert.HasCount(2, rows);
        Assert.IsFalse(rows[0].TryGetProperty("logging.dropped_field_count", out _));
        Assert.IsFalse(rows[0].TryGetProperty("{OriginalFormat}", out _));
        Assert.AreEqual(1, rows[1].GetProperty("logging.dropped_field_count").GetInt32());
        Assert.IsFalse(rows[1].TryGetProperty("tenant", out _));
    }

    [TestMethod]
    public void SurrogatePairIsNeverSplit()
    {
        using var output = new StringWriter();
        using var provider = new JsonLogProvider(new("shared-test", "development", "region-1", ["example.note"]), output);
        // 2 + 254 * 4 bytes fit the 1,021-byte budget; the next pair would split at byte 1,022.
        var text = "ab" + string.Concat(Enumerable.Repeat("\U0001F600", 400));
        // Separate records: the serializer escapes each pair as 12 bytes, which counts toward the line limit.
        var logger = provider.CreateLogger("test");
        logger.Log(LogLevel.Information, default, new Dictionary<string, object?>(), null, (_, _) => text);
        logger.Log(LogLevel.Information, default, new Dictionary<string, object?> { ["example.note"] = text }, null, (_, _) => "Note");
        Assert.AreEqual(0L, provider.DroppedRecords);
        var rows = Lines(provider, output).Select(l => JsonDocument.Parse(l).RootElement).ToArray();
        Assert.HasCount(2, rows);
        foreach (var value in new[] { rows[0].GetProperty("message").GetString()!, rows[1].GetProperty("example.note").GetString()! })
        {
            Assert.AreEqual("ab" + string.Concat(Enumerable.Repeat("\U0001F600", 254)) + "\u2026", value);
            Assert.AreEqual(1021, new UTF8Encoding(false, true).GetByteCount(value));
        }
        Assert.IsTrue(rows.All(r => r.GetProperty("logging.truncated").GetBoolean()));
    }

    [TestMethod]
    public void OversizeRecordShortensStackByWholeFramesBeforeRemovingFields()
    {
        using var output = new StringWriter();
        using var provider = new JsonLogProvider(new("shared-test", "development", "region-1", ["example.a", "example.b"]), output);
        var fields = new Dictionary<string, object?> { ["example.a"] = new string('a', 1000), ["example.b"] = new string('b', 1000) };
        provider.CreateLogger("test").Log(LogLevel.Error, default, fields, Caught("private", 60), (_, _) => new string('m', 1000));
        Assert.AreEqual(0L, provider.DroppedRecords);
        var line = Lines(provider, output).Single();
        var row = JsonDocument.Parse(line).RootElement;
        Assert.IsLessThanOrEqualTo(4096, Bytes(line));
        Assert.AreEqual(1000, row.GetProperty("example.a").GetString()!.Length);
        Assert.AreEqual(1000, row.GetProperty("example.b").GetString()!.Length);
        Assert.IsTrue(row.GetProperty("logging.truncated").GetBoolean());
        Assert.IsFalse(row.TryGetProperty("logging.dropped_field_count", out _));
        var frames = row.GetProperty("exception.stacktrace").GetString()!.Split('\n');
        Assert.IsTrue(frames.All(f => f.StartsWith("at OneNexus.Observability.Tests.DegradationTests.RaiseNested (DegradationTests.cs:", StringComparison.Ordinal)));
        Assert.IsEmpty(Contract.Validate(row));
    }

    [TestMethod]
    public void RequestFieldsAreNeverRemovedSoAnUnfittableRecordIsDropped()
    {
        using var output = new StringWriter();
        using var provider = new JsonLogProvider(new("shared-test", "development", "region-1", ["example.a"]), output);
        var fields = new Dictionary<string, object?>
        {
            ["http.route"] = new string('r', 1100), ["http.request.method"] = new string('g', 1100),
            ["error_code"] = new string('e', 1100), ["example.a"] = "small",
        };
        provider.CreateLogger("test").Log(LogLevel.Information, default, fields, null, (_, _) => new string('m', 1100));
        Assert.IsTrue(provider.CloseWithin(TimeSpan.FromSeconds(10)));
        Assert.AreEqual("", output.ToString());
        Assert.AreEqual(1L, provider.DroppedRecords);
    }
}
