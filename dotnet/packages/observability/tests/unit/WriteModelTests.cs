using System.Diagnostics;
using System.Text.Json;
using Microsoft.Extensions.Logging;
using Microsoft.VisualStudio.TestTools.UnitTesting;

namespace OneNexus.Observability.Tests;

/// <summary>The shared write model (design review F2; tests/logging/scenarios.json write_model).</summary>
[TestClass]
public sealed class WriteModelTests
{
    private static readonly LogConfiguration Config = new("write-test", "development", "region-1");
    private static readonly TimeSpan Long = TimeSpan.FromSeconds(10);

    private static JsonElement Model()
    {
        using var suite = JsonDocument.Parse(File.ReadAllBytes(Environment.GetEnvironmentVariable("ONENEXUS_LOGGING_SCENARIOS")!));
        return suite.RootElement.GetProperty("write_model").Clone();
    }

    private static int Lines(JsonElement model, string id) =>
        model.GetProperty("cases").EnumerateArray().Single(c => c.GetProperty("id").GetString() == id).GetProperty("lines").GetInt32();

    [TestMethod]
    public void ConstantsMatchTheSharedSpec()
    {
        var model = Model();
        Assert.AreEqual(JsonLogProvider.QueueCapacity, model.GetProperty("queue_capacity").GetInt32());
        Assert.AreEqual((int)JsonLogProvider.CloseTimeout.TotalMilliseconds, model.GetProperty("close_timeout_ms").GetInt32());
        var counters = model.GetProperty("counters").EnumerateArray().Select(c => c.GetString()!.Replace("_", "")).ToHashSet(StringComparer.OrdinalIgnoreCase);
        var fields = typeof(LogWriteStats).GetProperties().Select(p => p.Name).ToHashSet(StringComparer.OrdinalIgnoreCase);
        Assert.IsTrue(counters.SetEquals(fields));
        var dotnet = model.GetProperty("cases").EnumerateArray()
            .Where(c => c.GetProperty("languages").EnumerateArray().Any(l => l.GetString() == "dotnet"))
            .Select(c => c.GetProperty("id").GetString()).ToArray();
        CollectionAssert.AreEquivalent(
            new[] { "blocked_output_never_blocks_caller", "write_error_recovers", "close_drains", "close_deadline", "log_after_close" }, dotnet);
    }

    /// <summary>blocked_output_never_blocks_caller</summary>
    [TestMethod]
    public void BlockedOutputNeverBlocksCaller()
    {
        var model = Model();
        var lines = Lines(model, "blocked_output_never_blocks_caller");
        var budget = model.GetProperty("caller_budget_ms").GetInt32();
        using var output = new GateWriter();
        using var provider = new JsonLogProvider(Config, output);
        var logger = provider.CreateLogger("test");
        var slowest = TimeSpan.Zero;
        for (var i = 0; i < lines; i++)
        {
            var watch = Stopwatch.StartNew();
            logger.LogInformation("Line {attempt}", i);
            if (watch.Elapsed > slowest) slowest = watch.Elapsed;
        }
        Assert.IsLessThan(budget, slowest.TotalMilliseconds);
        var stats = provider.Stats;
        Assert.IsGreaterThanOrEqualTo(lines - JsonLogProvider.QueueCapacity - 1, stats.QueueFull);
        Assert.AreEqual(0L, stats.Written);
        output.Open.Set();
        Assert.IsTrue(provider.CloseWithin(Long));
        stats = provider.Stats;
        Assert.AreEqual(lines - stats.QueueFull, stats.Written);
        Assert.AreEqual(0L, stats.Pending);
        Assert.AreEqual(stats.QueueFull, provider.DroppedRecords);
        Assert.HasCount((int)stats.Written, output.ToString().Split('\n', StringSplitOptions.RemoveEmptyEntries));
    }

    /// <summary>write_error_recovers</summary>
    [TestMethod]
    public void WriteErrorRecovers()
    {
        var lines = Lines(Model(), "write_error_recovers");
        using var output = new FailFirstWriter();
        using var provider = new JsonLogProvider(Config, output);
        var logger = provider.CreateLogger("test");
        for (var i = 0; i < lines; i++) logger.LogInformation("Line {attempt}", i);
        Assert.IsTrue(provider.CloseWithin(Long));
        var stats = provider.Stats;
        Assert.AreEqual(1L, stats.IoErrors);
        Assert.AreEqual(lines - 1L, stats.Written);
        Assert.AreEqual(1L, provider.DroppedRecords);
        var rows = output.ToString().Split('\n', StringSplitOptions.RemoveEmptyEntries).Select(l => JsonDocument.Parse(l).RootElement.GetProperty("message").GetString()).ToArray();
        CollectionAssert.AreEqual(Enumerable.Range(1, lines - 1).Select(i => $"Line {i}").ToArray(), rows);
    }

    /// <summary>close_drains</summary>
    [TestMethod]
    public void CloseDrains()
    {
        var lines = Lines(Model(), "close_drains");
        using var output = new SlowWriter();
        using var provider = new JsonLogProvider(Config, output);
        var logger = provider.CreateLogger("test");
        for (var i = 0; i < lines; i++) logger.LogInformation("Line {attempt}", i);
        Assert.IsTrue(provider.CloseWithin(JsonLogProvider.CloseTimeout));
        var stats = provider.Stats;
        Assert.AreEqual((long)lines, stats.Written);
        Assert.AreEqual(0L, stats.Pending);
        Assert.HasCount(lines, output.ToString().Split('\n', StringSplitOptions.RemoveEmptyEntries));
    }

    /// <summary>close_deadline</summary>
    [TestMethod]
    public void CloseDeadline()
    {
        var model = Model();
        var lines = Lines(model, "close_deadline");
        using var output = new GateWriter();
        var provider = new JsonLogProvider(Config, output);
        var logger = provider.CreateLogger("test");
        for (var i = 0; i < lines; i++) logger.LogInformation("Line {attempt}", i);
        var watch = Stopwatch.StartNew();
        Assert.IsFalse(provider.CloseWithin(JsonLogProvider.CloseTimeout));
        Assert.IsLessThan(model.GetProperty("close_timeout_ms").GetInt32() + 500, watch.Elapsed.TotalMilliseconds);
        Assert.IsGreaterThanOrEqualTo(lines - 1L, provider.Stats.Pending); // Undelivered lines stay counted.
        Assert.AreEqual(0L, provider.Stats.Written);
        var again = Stopwatch.StartNew();
        provider.Dispose(); // A second close is harmless and does not wait again.
        Assert.IsLessThan(500, again.Elapsed.TotalMilliseconds);
        output.Open.Set();
    }

    /// <summary>log_after_close</summary>
    [TestMethod]
    public void LogAfterClose()
    {
        var lines = Lines(Model(), "log_after_close");
        using var output = new StringWriter();
        var provider = new JsonLogProvider(Config, output);
        var logger = provider.CreateLogger("test");
        provider.Dispose();
        for (var i = 0; i < lines; i++) logger.LogInformation("Too late");
        var stats = provider.Stats;
        Assert.AreEqual((long)lines, stats.Closed);
        Assert.AreEqual(0L, stats.Written);
        Assert.AreEqual("", output.ToString());
        Assert.IsTrue(provider.CloseWithin(Long)); // A second close is harmless.
        provider.Dispose();
    }

    [TestMethod]
    public async Task CloseRacingConcurrentLogCallsLosesNothing()
    {
        for (var round = 0; round < 20; round++)
        {
            using var output = new StringWriter();
            using var provider = new JsonLogProvider(Config, output);
            var logger = provider.CreateLogger("test");
            using var start = new ManualResetEventSlim();
            var callers = Enumerable.Range(0, 8).Select(_ => Task.Run(() =>
            {
                start.Wait();
                for (var i = 0; i < 200; i++) logger.LogInformation("Race");
            })).ToArray();
            start.Set();
            await Task.Delay(round % 3);
            Assert.IsTrue(provider.CloseWithin(Long)); // Nothing stuck: a close never reports a loss.
            await Task.WhenAll(callers).WaitAsync(Long);
            var stats = provider.Stats;
            Assert.AreEqual(8L * 200, stats.Written + stats.Closed + stats.QueueFull);
            Assert.AreEqual(0L, stats.Pending);
            Assert.AreEqual(0L, stats.IoErrors + stats.Invalid);
        }
    }

    [TestMethod]
    public void RejectedRecordsAreCountedOnTheCallerThread()
    {
        using var output = new GateWriter();
        using var provider = new JsonLogProvider(Config, output);
        provider.CreateLogger("test").Log(LogLevel.Information, default, "safe", null, (_, _) => throw new InvalidOperationException("private"));
        Assert.AreEqual(1L, provider.Stats.Invalid); // Counted before the blocked writer ever runs.
        output.Open.Set();
    }

    /// <summary>Blocks every write until <see cref="Open"/> is set.</summary>
    private sealed class GateWriter : StringWriter
    {
        public ManualResetEventSlim Open { get; } = new();
        public override void WriteLine(string? value)
        {
            Open.Wait();
            lock (this) base.WriteLine(value);
        }
        public override string ToString() { lock (this) return base.ToString(); }
    }

    /// <summary>The first write fails; later writes succeed.</summary>
    private sealed class FailFirstWriter : StringWriter
    {
        private int calls;
        public override void WriteLine(string? value)
        {
            if (Interlocked.Increment(ref calls) == 1) throw new IOException("private sink detail");
            base.WriteLine(value);
        }
    }

    /// <summary>Each write takes a few milliseconds.</summary>
    private sealed class SlowWriter : StringWriter
    {
        public override void WriteLine(string? value)
        {
            Thread.Sleep(20);
            base.WriteLine(value);
        }
    }
}
