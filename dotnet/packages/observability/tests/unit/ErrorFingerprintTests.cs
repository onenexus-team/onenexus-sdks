using System.Text.Json;
using Microsoft.Extensions.Logging;
using Microsoft.VisualStudio.TestTools.UnitTesting;
using OneNexus.Observability.Rules;

namespace OneNexus.Observability.Tests;

/// <summary>Error fingerprint (tests/logging/scenarios.json error_fingerprint, design review F1).</summary>
[TestClass]
public sealed class ErrorFingerprintTests
{
    private static JsonElement Spec()
    {
        using var suite = JsonDocument.Parse(File.ReadAllBytes(Environment.GetEnvironmentVariable("ONENEXUS_LOGGING_SCENARIOS")!));
        return suite.RootElement.GetProperty("error_fingerprint").Clone();
    }

    private static string Field => Spec().GetProperty("field").GetString()!;

    private static Exception Failure()
    {
        try { throw new InvalidOperationException("private-sentinel"); }
        catch (InvalidOperationException ex) { return ex; }
    }

    /// <summary>Logs each call; the shared degradation allowlist lets a caller supply the stack.</summary>
    private static JsonElement[] Rows(params (string Message, List<KeyValuePair<string, object?>> Fields, Exception? Error)[] calls)
    {
        using var output = new StringWriter();
        using var provider = new JsonLogProvider(
            new("dotnet-fingerprint", "development", "region-1", ["shared.note", "exception.stacktrace"]), output);
        var logger = provider.CreateLogger("fingerprint");
        foreach (var (message, fields, error) in calls)
            logger.Log(LogLevel.Error, default, fields, error, (_, _) => message);
        Assert.IsTrue(provider.CloseWithin(TimeSpan.FromSeconds(10)));
        Assert.AreEqual(0L, provider.Stats.Invalid);
        return output.ToString().Split('\n', StringSplitOptions.RemoveEmptyEntries)
            .Select(line => JsonDocument.Parse(line).RootElement.Clone()).ToArray();
    }

    private static string? Text(JsonElement row, string key) =>
        row.TryGetProperty(key, out var value) ? value.GetString() : null;

    /// <summary>type_only, frames, line_numbers_ignored, frame_without_file, type_changes_fingerprint, multibyte</summary>
    [TestMethod]
    public void Vectors()
    {
        foreach (var item in Spec().GetProperty("cases").EnumerateArray())
            Assert.AreEqual(item.GetProperty("fingerprint").GetString(),
                JsonLogProvider.ErrorFingerprint(item.GetProperty("error_type").GetString()!, item.GetProperty("stacktrace").GetString()),
                item.GetProperty("id").GetString());
    }

    /// <summary>logged_error_has_fingerprint</summary>
    [TestMethod]
    public void LoggedErrorHasFingerprint()
    {
        var row = Rows(("Job failed", [], Failure())).Single();
        Assert.AreEqual(JsonLogProvider.ErrorFingerprint(Text(row, "error.type")!, Text(row, "exception.stacktrace")), Text(row, Field));
        Assert.DoesNotContain("private-sentinel", row.GetRawText());
        Assert.IsEmpty(Contract.Validate(row));
    }

    /// <summary>same_error_same_fingerprint</summary>
    [TestMethod]
    public void SameErrorSameFingerprint()
    {
        var error = Failure();
        var rows = Rows(("Job failed", [], error), ("Job failed", [], error));
        Assert.IsNotNull(Text(rows[0], Field));
        Assert.AreEqual(Text(rows[0], Field), Text(rows[1], Field));
    }

    /// <summary>stable_when_fitted</summary>
    [TestMethod]
    public void StableWhenFitted()
    {
        var stack = string.Join('\n', Enumerable.Range(0, 55).Select(i => $"at function_{i} (deep_module.py:{i})"));
        Assert.IsLessThan(2048, stack.Length); // whole: only fitting can shorten it
        var row = Rows((new string('x', 1000),
            [new("exception.stacktrace", stack), new("shared.note", new string('n', 1000))], Failure())).Single();
        Assert.AreNotEqual(stack, Text(row, "exception.stacktrace")); // the record was fitted
        Assert.IsTrue(row.GetProperty("logging.truncated").GetBoolean());
        Assert.AreEqual(JsonLogProvider.ErrorFingerprint(Text(row, "error.type")!, stack), Text(row, Field));
    }

    /// <summary>caller_value_removed</summary>
    [TestMethod]
    public void CallerValueRemoved()
    {
        var row = Rows(("Job failed", [new(Field, "0000000000000000")], Failure())).Single();
        Assert.IsNotNull(Text(row, Field));
        Assert.AreNotEqual("0000000000000000", Text(row, Field));
        Assert.AreEqual(1, row.GetProperty("logging.dropped_field_count").GetInt32());
    }

    /// <summary>no_error_no_fingerprint</summary>
    [TestMethod]
    public void NoErrorNoFingerprint()
    {
        var row = Rows(("Job done", [], null)).Single();
        Assert.IsFalse(row.TryGetProperty(Field, out _));
    }
}
