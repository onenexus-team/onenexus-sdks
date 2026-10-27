using System.Diagnostics;
using System.Text.Json;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;
using Microsoft.VisualStudio.TestTools.UnitTesting;
using OneNexus.LogContract;

namespace OneNexus.Observability.Tests;

[TestClass]
public sealed partial class LoggingTests
{
    private const string Parent = "00-11111111111111111111111111111111-2222222222222222-01";
    private static readonly LogConfiguration Config = new("cas-test", "development", "region-1", ["operation_id", "attempt"]);
    private static KeyValuePair<string, string>[] Headers(string parent = Parent) => [new("traceparent", parent)];
    private static JsonElement[] Records(StringWriter writer) => writer.ToString().Split('\n', StringSplitOptions.RemoveEmptyEntries).Select(s => JsonDocument.Parse(s).RootElement.Clone()).ToArray();

    [TestMethod]
    public void CommonFieldsAndSafeCustomFields()
    {
        using var output = new StringWriter();
        using var provider = new JsonLogProvider(Config, output);
        var logger = provider.CreateLogger("test");
        using (CorrelationContext.BindIncoming(Headers(), true))
        using (logger.BeginScope(new Dictionary<string, object?> { ["operation_id"] = "op-1", ["environment"] = "prod", ["Authorization"] = "private-marker" }))
        {
            logger.LogWarning("Request {attempt}", 2);
            logger.LogError(new InvalidOperationException("private-exception"), "Safe failure");
        }
        logger.LogInformation("System ready");
        var rows = Records(output);
        Assert.HasCount(3, rows);
        Assert.AreEqual("development", rows[0].GetProperty("environment").GetString());
        Assert.AreEqual("WARN", rows[0].GetProperty("level").GetString());
        Assert.AreEqual("op-1", rows[0].GetProperty("operation_id").GetString());
        Assert.AreEqual(2, rows[0].GetProperty("attempt").GetInt32());
        Assert.AreEqual("11111111111111111111111111111111", rows[0].GetProperty("trace_id").GetString());
        Assert.IsFalse(rows[2].TryGetProperty("trace_id", out _));
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
        var rows = Records(output);
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
        Assert.HasCount(1, Records(output));
    }

    [TestMethod]
    public void InvalidRecordsAndSinkFailuresAreCountedWithoutEcho()
    {
        using var output = new StringWriter();
        using var provider = new JsonLogProvider(Config, output);
        var logger = provider.CreateLogger("test");
        logger.LogInformation(new string('界', 400));
        logger.LogInformation("Invalid {attempt}", double.NaN);
        logger.Log(LogLevel.Information, default, "safe", null, (_, _) => throw new InvalidOperationException("private"));
        using (logger.BeginScope(new Dictionary<string, object?> { ["event"] = "request.done" }))
            logger.LogInformation("Incomplete event");
        Assert.AreEqual(4L, provider.DroppedRecords);
        Assert.AreEqual("", output.ToString());
        using var broken = new JsonLogProvider(Config, new BrokenWriter());
        broken.CreateLogger("test").LogInformation("safe");
        Assert.AreEqual(1L, broken.DroppedRecords);
        provider.Dispose();
        logger.LogInformation("After dispose");
        Assert.AreEqual(5L, provider.DroppedRecords);
        output.Write("Writer still owned by caller");
    }

    private sealed class BrokenWriter : StringWriter
    {
        public override void WriteLine(string? value) => throw new IOException("private sink detail");
    }

    [LoggerMessage(EventId = 42, Level = LogLevel.Information, Message = "Attempt {attempt} completed")]
    private static partial void GeneratedLog(ILogger logger, int attempt);

    [TestMethod]
    public void SourceGeneratedLoggerUsesSameProvider()
    {
        using var output = new StringWriter();
        using var provider = new JsonLogProvider(Config, output);
        using (CorrelationContext.BindIncoming(Headers(), true)) GeneratedLog(provider.CreateLogger("cas"), 2);
        var record = Records(output).Single();
        Assert.IsEmpty(Contract.Validate(record, "correlated"));
        Assert.AreEqual(2, record.GetProperty("attempt").GetInt32());
        Assert.AreEqual("Attempt 2 completed", record.GetProperty("message").GetString());
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
        var row = Records(output).Single();
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
        CollectionAssert.AreEqual(new[] { "TRACE", "DEBUG", "INFO", "WARN", "ERROR", "FATAL" }, Records(output).Select(r => r.GetProperty("level").GetString()).ToArray());
        using (logger.BeginScope(new Dictionary<string, object?> { ["operation_id"] = new string('x', 4096) }))
            logger.LogInformation("Large custom field");
        Assert.AreEqual(1L, provider.DroppedRecords);
        Assert.HasCount(6, Records(output));
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
        Assert.HasCount(1, Records(output));
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
