using System.Diagnostics;
using System.Text.Json;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;
using Microsoft.VisualStudio.TestTools.UnitTesting;
using OneNexus.Observability.Rules;

namespace OneNexus.Observability.Tests;

[TestClass]
public sealed partial class LoggingTests
{
    private const string Parent = "00-11111111111111111111111111111111-2222222222222222-01";
    private static readonly LogConfiguration Config = new("cas-test", "development", "region-1", ["example.operation_id", "job.attempt", "logger"]);
    private static KeyValuePair<string, string>[] Headers(string parent = Parent) => [new("traceparent", parent)];
    // Writes are asynchronous (write model F2): drain the provider before reading its output.
    private static JsonElement[] Records(JsonLogProvider provider, StringWriter writer)
    {
        Assert.IsTrue(provider.CloseWithin(TimeSpan.FromSeconds(10)));
        return Records(writer);
    }
    private static JsonElement[] Records(StringWriter writer) => writer.ToString().Split('\n', StringSplitOptions.RemoveEmptyEntries).Select(s => JsonDocument.Parse(s).RootElement.Clone()).ToArray();

    [TestMethod]
    public void SharedEmissionScenarios()
    {
        using var suite = JsonDocument.Parse(File.ReadAllBytes(Environment.GetEnvironmentVariable("ONENEXUS_LOGGING_SCENARIOS")!));
        var cases = suite.RootElement.GetProperty("emission_cases");
        Assert.IsTrue(cases.GetArrayLength() > 0);
        foreach (var item in cases.EnumerateArray())
        {
            using var output = new StringWriter();
            using var provider = new JsonLogProvider(new("shared-test", "development", "region-1"), output);
            var logger = provider.CreateLogger("shared");
            var parent = item.GetProperty("traceparent").GetString();
            using (CorrelationContext.BindIncoming(parent is null ? [] : Headers(parent), true))
                logger.Log(LogLevel.Information, new EventId(), item.GetProperty("message").GetString()!, null, (message, _) => message);
            var rows = Records(provider, output);
            Assert.HasCount(1, rows);
            foreach (var expected in item.GetProperty("expected").EnumerateObject())
                Assert.AreEqual(expected.Value.GetString(), rows[0].GetProperty(expected.Name).GetString());
            if (item.TryGetProperty("absent", out var absent))
                foreach (var key in absent.EnumerateArray()) Assert.IsFalse(rows[0].TryGetProperty(key.GetString()!, out _));
            Assert.IsEmpty(Contract.Validate(rows[0]));
        }
    }

    [TestMethod]
    public void CommonFieldsAndSafeCustomFields()
    {
        using var output = new StringWriter();
        using var provider = new JsonLogProvider(Config, output);
        var logger = provider.CreateLogger("test");
        using (CorrelationContext.BindIncoming(Headers(), true))
        using (logger.BeginScope(new Dictionary<string, object?> { ["example.operation_id"] = "op-1", ["environment"] = "prod", ["Authorization"] = "private-marker" }))
        {
            logger.LogWarning("Request {job.attempt}", 2);
            logger.LogError(new InvalidOperationException("private-exception"), "Safe failure");
        }
        logger.LogInformation("System ready");
        var rows = Records(provider, output);
        Assert.HasCount(3, rows);
        Assert.AreEqual("development", rows[0].GetProperty("environment").GetString());
        Assert.AreEqual("WARN", rows[0].GetProperty("level").GetString());
        Assert.AreEqual("op-1", rows[0].GetProperty("example.operation_id").GetString());
        Assert.AreEqual(2, rows[0].GetProperty("job.attempt").GetInt32());
        Assert.AreEqual("11111111111111111111111111111111", rows[0].GetProperty("trace_id").GetString());
        // The protected "environment" and unapproved "Authorization" scope fields are removed and counted.
        Assert.IsTrue(rows[..2].All(r => r.GetProperty("logging.dropped_field_count").GetInt32() == 2));
        Assert.AreEqual("System.InvalidOperationException", rows[1].GetProperty("error.type").GetString());
        Assert.IsFalse(rows[1].TryGetProperty("exception.stacktrace", out _)); // Never thrown: no frames.
        Assert.IsFalse(rows[2].TryGetProperty("trace_id", out _));
        Assert.IsFalse(rows[2].TryGetProperty("logging.dropped_field_count", out _));
        Assert.IsFalse(output.ToString().Contains("private", StringComparison.Ordinal));
        Assert.IsTrue(rows.All(r => Contract.Validate(r).Count == 0));
        Assert.AreEqual(0L, provider.DroppedRecords);
    }

    [TestMethod]
    public void MissingInvalidAndUntrustedContextsStayUncorrelatedEvenWithFrameworkActivity()
    {
        using var activity = new Activity("framework").SetIdFormat(ActivityIdFormat.W3C).Start();
        foreach (var header in new[] { "", "bad", "00-00000000000000000000000000000000-2222222222222222-01", Parent.Replace('1', 'A'), Parent + "," + Parent })
            using (CorrelationContext.BindIncoming(Headers(header), true))
            {
                Assert.IsNull(CorrelationContext.TraceId);
                Assert.IsEmpty(CorrelationContext.OutgoingHeaders());
            }
        using (CorrelationContext.BindIncoming(Headers(), false)) Assert.IsNull(CorrelationContext.TraceId);
        using (CorrelationContext.BindIncoming([new("traceparent", Parent), new("Traceparent", Parent)], true)) Assert.IsNull(CorrelationContext.TraceId);
        using (CorrelationContext.BindUncorrelated()) Assert.IsNull(CorrelationContext.TraceId);
        Assert.AreSame(activity, Activity.Current);
    }

    [TestMethod]
    public void NestedScopesExceptionsRetriesAndSampling()
    {
        Assert.IsNull(CorrelationContext.TraceId);
        using (CorrelationContext.BindIncoming(Headers(), true))
        {
            Assert.AreEqual(Parent, CorrelationContext.OutgoingHeaders()["traceparent"]);
            Assert.ThrowsExactly<InvalidOperationException>(() =>
            {
                using var empty = CorrelationContext.BindUncorrelated();
                throw new InvalidOperationException("test");
            });
            Assert.AreEqual("11111111111111111111111111111111", CorrelationContext.TraceId);
            var saved = JsonSerializer.Serialize(CorrelationContext.OutgoingHeaders());
            for (var attempt = 0; attempt < 2; attempt++)
                using (CorrelationContext.BindIncoming(JsonSerializer.Deserialize<Dictionary<string, string>>(saved)!, true))
                    Assert.AreEqual(Parent, CorrelationContext.OutgoingHeaders()["traceparent"]);
        }
        Assert.IsNull(CorrelationContext.TraceId);
        using (CorrelationContext.BindIncoming(Headers(), true, preserveSampling: false))
            Assert.EndsWith("-00", CorrelationContext.OutgoingHeaders()["traceparent"]);
    }

    [TestMethod]
    public async Task ConcurrentRequestsCancellationAndParallelWrites()
    {
        using var output = new StringWriter();
        using var provider = new JsonLogProvider(Config, output);
        var logger = provider.CreateLogger("test");
        var ready = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
        using var cancel = new CancellationTokenSource();
        var cancelled = Task.Run(async () =>
        {
            try
            {
                using var scope = CorrelationContext.BindIncoming(Headers(), true);
                logger.LogInformation("Waiting");
                ready.SetResult();
                await Task.Delay(Timeout.Infinite, cancel.Token);
            }
            finally { Assert.IsNull(CorrelationContext.TraceId); }
        });
        await ready.Task.WaitAsync(TimeSpan.FromSeconds(5));
        var other = "00-33333333333333333333333333333333-4444444444444444-00";
        using (CorrelationContext.BindIncoming(Headers(other), true))
        {
            cancel.Cancel();
            await Assert.ThrowsAsync<OperationCanceledException>(async () => await cancelled);
            await Task.WhenAll(Enumerable.Range(0, 32).Select(_ => Task.Run(() => logger.LogInformation("Other"))));
            Assert.AreEqual(other[3..35], CorrelationContext.TraceId);
        }
        var rows = Records(provider, output);
        Assert.HasCount(33, rows);
        Assert.AreEqual(Parent[3..35], rows[0].GetProperty("trace_id").GetString());
        Assert.IsTrue(rows.Skip(1).All(r => r.GetProperty("trace_id").GetString() == other[3..35]));
        Assert.AreEqual(0L, provider.DroppedRecords);
        Assert.IsNull(CorrelationContext.TraceId);
    }

    [TestMethod]
    public void ExistingActivityChildRetainsTraceAndSampling()
    {
        using var scope = CorrelationContext.BindIncoming(Headers(), true);
        using var activity = new Activity("existing-instrumentation").SetParentId(Parent).Start();
        Assert.AreEqual(activity.TraceId.ToHexString(), CorrelationContext.TraceId);
        Assert.AreEqual(activity.Id, CorrelationContext.OutgoingHeaders()["traceparent"]);
        Assert.IsTrue(activity.Recorded);
        Assert.HasCount(1, CorrelationContext.OutgoingHeaders());
    }

    [TestMethod]
    public void BadConfigurationAndDuplicateInstallation()
    {
        Assert.ThrowsExactly<ArgumentException>(() => new LogConfiguration("cas", "dev", "r1"));
        Assert.ThrowsExactly<ArgumentException>(() => new LogConfiguration("cas", "prod", "r1", ["trace_id"]));
        using var output = new StringWriter();
        var services = new ServiceCollection();
        services.AddLogging(builder =>
        {
            builder.AddOneNexus(Config, output).AddOneNexus(Config, output);
            Assert.ThrowsExactly<InvalidOperationException>(() => builder.AddOneNexus(new("other", "prod", "r2"), output));
        });
        using var container = services.BuildServiceProvider();
        Assert.HasCount(1, container.GetServices<ILoggerProvider>());
        container.GetRequiredService<ILoggerFactory>().CreateLogger("test").LogInformation("Once");
        container.Dispose(); // Disposing the container drains the provider.
        Assert.HasCount(1, Records(output));
    }

    [TestMethod]
    public void InvalidRecordsAndSinkFailuresAreCountedWithoutEcho()
    {
        using var output = new StringWriter();
        using var provider = new JsonLogProvider(Config, output);
        var logger = provider.CreateLogger("test");
        logger.LogInformation(new string('界', 400)); // Shortened, not dropped.
        logger.LogInformation("Invalid {job.attempt}", double.NaN); // Field removed and counted, not dropped.
        logger.Log(LogLevel.Information, default, "safe", null, (_, _) => throw new InvalidOperationException("private"));
        using (logger.BeginScope(new Dictionary<string, object?> { ["event"] = "request.done" }))
            logger.LogInformation("Incomplete event");
        logger.LogInformation("");
        Assert.AreEqual(3L, provider.DroppedRecords);
        var kept = Records(provider, output);
        Assert.HasCount(2, kept);
        Assert.IsTrue(kept[0].GetProperty("logging.truncated").GetBoolean());
        Assert.AreEqual(new string('界', 340) + "\u2026", kept[0].GetProperty("message").GetString());
        Assert.IsFalse(kept[1].TryGetProperty("job.attempt", out _));
        Assert.AreEqual(1, kept[1].GetProperty("logging.dropped_field_count").GetInt32());
        using var broken = new JsonLogProvider(Config, new BrokenWriter());
        broken.CreateLogger("test").LogInformation("safe");
        Assert.IsTrue(broken.CloseWithin(TimeSpan.FromSeconds(10)));
        Assert.AreEqual(1L, broken.DroppedRecords);
        Assert.AreEqual(1L, broken.Stats.IoErrors);
        provider.Dispose();
        logger.LogInformation("After dispose");
        Assert.AreEqual(4L, provider.DroppedRecords);
        output.Write("Writer still owned by caller");
    }

    private sealed class BrokenWriter : StringWriter
    {
        public override void WriteLine(string? value) => throw new IOException("private sink detail");
    }

    // A generated template name is a parameter name, so it can only carry a flat registered field.
    [LoggerMessage(EventId = 42, Level = LogLevel.Information, Message = "Worker {logger} completed")]
    private static partial void GeneratedLog(ILogger log, string logger);

    [TestMethod]
    public void SourceGeneratedLoggerUsesSameProvider()
    {
        using var output = new StringWriter();
        using var provider = new JsonLogProvider(Config, output);
        using (CorrelationContext.BindIncoming(Headers(), true)) GeneratedLog(provider.CreateLogger("cas"), "app.worker");
        var record = Records(provider, output).Single();
        Assert.IsEmpty(Contract.Validate(record, "correlated"));
        Assert.AreEqual("app.worker", record.GetProperty("logger").GetString());
        Assert.IsFalse(record.TryGetProperty("logging.dropped_field_count", out _)); // {OriginalFormat} is not a caller field.
        Assert.AreEqual("Worker app.worker completed", record.GetProperty("message").GetString());
    }

    [TestMethod]
    public void ScopeExitOrderAndIndependentUncorrelatedEvents()
    {
        var outer = CorrelationContext.BindIncoming(Headers(), true);
        var inner = CorrelationContext.BindUncorrelated();
        Assert.ThrowsExactly<InvalidOperationException>(outer.Dispose);
        inner.Dispose();
        Assert.AreEqual(Parent[3..35], CorrelationContext.TraceId);
        outer.Dispose();
        outer.Dispose();
        Assert.IsNull(CorrelationContext.TraceId);
        using var output = new StringWriter();
        using var provider = new JsonLogProvider(Config, output);
        var logger = provider.CreateLogger("test");
        using (CorrelationContext.BindIncoming([], true))
        using (logger.BeginScope(new Dictionary<string, object?> { ["event"] = "request.completed", ["outcome"] = "success" }))
            logger.LogInformation("Request without correlation");
        var row = Records(provider, output).Single();
        Assert.IsFalse(row.TryGetProperty("trace_id", out _));
        Assert.IsEmpty(Contract.Validate(row, "common"));
        Assert.AreEqual(0L, provider.DroppedRecords);
    }

    [TestMethod]
    public void LevelMappingAndBoundedRecordSize()
    {
        using var output = new StringWriter();
        using var provider = new JsonLogProvider(Config, output);
        var logger = provider.CreateLogger("test");
        foreach (var level in Enum.GetValues<LogLevel>()) logger.Log(level, "Safe message");
        using (logger.BeginScope(new Dictionary<string, object?> { ["example.operation_id"] = new string('x', 4096) }))
            logger.LogInformation("Large custom field");
        var rows = Records(provider, output);
        Assert.AreEqual(0L, provider.DroppedRecords);
        Assert.HasCount(7, rows);
        CollectionAssert.AreEqual(new[] { "TRACE", "DEBUG", "INFO", "WARN", "ERROR", "FATAL" }, rows[..6].Select(r => r.GetProperty("level").GetString()).ToArray());
        Assert.AreEqual(new string('x', 1021) + "\u2026", rows[6].GetProperty("example.operation_id").GetString());
        Assert.IsTrue(rows[6].GetProperty("logging.truncated").GetBoolean());
        Assert.IsTrue(rows.All(r => System.Text.Encoding.UTF8.GetByteCount(r.GetRawText()) <= Contract.MaxRecordBytes));
    }

    [TestMethod]
    public async Task DisposeWaitsForInFlightWriteAndRejectsLaterWrites()
    {
        using var output = new BlockingWriter();
        var provider = new JsonLogProvider(Config, output);
        var logger = provider.CreateLogger("test");
        var writing = Task.Run(() => logger.LogInformation("In flight"));
        await output.Entered.Task.WaitAsync(TimeSpan.FromSeconds(5));
        var disposing = Task.Run(provider.Dispose);
        output.Release.Set();
        await Task.WhenAll(writing, disposing).WaitAsync(TimeSpan.FromSeconds(5));
        logger.LogInformation("Too late");
        Assert.HasCount(1, Records(provider, output));
        Assert.AreEqual(1L, provider.DroppedRecords);
    }

    private sealed class BlockingWriter : StringWriter
    {
        public TaskCompletionSource Entered { get; } = new(TaskCreationOptions.RunContinuationsAsynchronously);
        public ManualResetEventSlim Release { get; } = new();
        public override void WriteLine(string? value)
        {
            Entered.SetResult();
            if (!Release.Wait(TimeSpan.FromSeconds(5))) throw new TimeoutException();
            base.WriteLine(value);
        }
        protected override void Dispose(bool disposing)
        {
            if (disposing) Release.Dispose();
            base.Dispose(disposing);
        }
    }
}
