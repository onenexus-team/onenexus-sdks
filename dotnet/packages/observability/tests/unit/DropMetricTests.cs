using System.Diagnostics.Metrics;
using System.Text.Json;
using Microsoft.Extensions.Logging;
using Microsoft.VisualStudio.TestTools.UnitTesting;

namespace OneNexus.Observability.Tests;

/// <summary>One drop metric (design review R1; tests/logging/scenarios.json drop_metric). Each test uses its own service.</summary>
[TestClass]
public sealed class DropMetricTests
{
    private static readonly TimeSpan Long = TimeSpan.FromSeconds(10);

    private static JsonElement Metric()
    {
        using var suite = JsonDocument.Parse(File.ReadAllBytes(Environment.GetEnvironmentVariable("ONENEXUS_LOGGING_SCENARIOS")!));
        return suite.RootElement.GetProperty("drop_metric").Clone();
    }

    private static JsonLogProvider Provider(string service, TextWriter output) => new(new LogConfiguration(service, "development", "region-1"), output);

    private static Dictionary<string, long> Rows(string service) =>
        LogDropMetrics.Snapshot().Where(row => row.Service == service).ToDictionary(row => row.Reason, row => row.Count);

    private static Dictionary<string, long> Expected(LogWriteStats stats) => new()
    {
        ["closed"] = stats.Closed, ["invalid"] = stats.Invalid, ["io_errors"] = stats.IoErrors, ["queue_full"] = stats.QueueFull,
    };

    private static Dictionary<string, long> Sum(LogWriteStats a, LogWriteStats b) =>
        Expected(a).ToDictionary(pair => pair.Key, pair => pair.Value + Expected(b)[pair.Key]);

    private static void Reject(JsonLogProvider provider) =>
        provider.CreateLogger("test").Log(LogLevel.Information, default, "safe", null, (_, _) => throw new InvalidOperationException("private"));

    [TestMethod]
    public void NamesMatchTheSharedSpec()
    {
        var metric = Metric();
        Assert.AreEqual(LogDropMetrics.InstrumentName, metric.GetProperty("otel_name").GetString());
        Assert.AreEqual(LogDropMetrics.Unit, metric.GetProperty("otel_unit").GetString());
        Assert.AreEqual(LogDropMetrics.PrometheusName, metric.GetProperty("prometheus_name").GetString());
        Assert.AreEqual(LogDropMetrics.Description, metric.GetProperty("help").GetString());
        CollectionAssert.AreEqual(metric.GetProperty("labels").EnumerateArray().Select(l => l.GetString()).ToArray(),
            new[] { LogDropMetrics.ServiceLabel, LogDropMetrics.ReasonLabel });
        CollectionAssert.AreEqual(metric.GetProperty("reasons").EnumerateArray().Select(r => r.GetString()).ToArray(), LogDropMetrics.ReasonNames.ToArray());
    }

    /// <summary>every_reason_reported_from_first_handler</summary>
    [TestMethod]
    public void EveryReasonReportedFromFirstHandler()
    {
        using var provider = Provider("drop-first", new StringWriter());
        CollectionAssert.AreEqual(
            LogDropMetrics.ReasonNames.Select(reason => new LogDropCount("drop-first", reason, 0)).ToArray(),
            LogDropMetrics.Snapshot().Where(row => row.Service == "drop-first").ToArray());
    }

    /// <summary>each_reason_counted</summary>
    [TestMethod]
    public void EachReasonCounted()
    {
        using (var invalid = Provider("drop-each-invalid", new StringWriter()))
        {
            Reject(invalid);
            Assert.AreEqual(1L, invalid.Stats.Invalid);
            CollectionAssert.AreEquivalent(Expected(invalid.Stats), Rows("drop-each-invalid"));
        }

        using (var failing = Provider("drop-each-io", new FailFirstWriter()))
        {
            failing.CreateLogger("test").LogInformation("Fails");
            Assert.IsTrue(failing.CloseWithin(Long));
            Assert.AreEqual(1L, failing.Stats.IoErrors);
            CollectionAssert.AreEquivalent(Expected(failing.Stats), Rows("drop-each-io"));
        }

        var late = Provider("drop-each-closed", new StringWriter());
        late.Dispose();
        late.CreateLogger("test").LogInformation("Too late");
        Assert.AreEqual(1L, late.Stats.Closed);
        CollectionAssert.AreEquivalent(Expected(late.Stats), Rows("drop-each-closed"));

        using var output = new GateWriter();
        using (var blocked = Provider("drop-each-full", output))
        {
            var logger = blocked.CreateLogger("test");
            for (var i = 0; i < JsonLogProvider.QueueCapacity + 10; i++) logger.LogInformation("Line {attempt}", i);
            Assert.IsGreaterThanOrEqualTo(9L, blocked.Stats.QueueFull);
            CollectionAssert.AreEquivalent(Expected(blocked.Stats), Rows("drop-each-full"));
            output.Open.Set();
        }
    }

    /// <summary>handlers_of_one_service_are_summed</summary>
    [TestMethod]
    public void HandlersOfOneServiceAreSummed()
    {
        using var first = Provider("drop-summed", new StringWriter());
        using var second = Provider("drop-summed", new StringWriter());
        Reject(first);
        Reject(second);
        Reject(second);
        second.Dispose();
        second.CreateLogger("test").LogInformation("Too late");
        Assert.HasCount(LogDropMetrics.ReasonNames.Count, Rows("drop-summed"));
        var expected = Sum(first.Stats, second.Stats);
        Assert.AreEqual(3L, expected["invalid"]);
        Assert.AreEqual(1L, expected["closed"]);
        CollectionAssert.AreEquivalent(expected, Rows("drop-summed"));
    }

    /// <summary>services_are_separate</summary>
    [TestMethod]
    public void ServicesAreSeparate()
    {
        using var a = Provider("drop-separate-a", new StringWriter());
        using var b = Provider("drop-separate-b", new StringWriter());
        var before = Rows("drop-separate-b");
        Reject(a);
        Reject(a);
        CollectionAssert.AreEquivalent(Expected(a.Stats), Rows("drop-separate-a"));
        Assert.AreEqual(2L, Rows("drop-separate-a")["invalid"]);
        CollectionAssert.AreEquivalent(before, Rows("drop-separate-b"));
        CollectionAssert.AreEquivalent(Expected(b.Stats), Rows("drop-separate-b"));
    }

    /// <summary>counts_survive_close</summary>
    [TestMethod]
    public void CountsSurviveClose()
    {
        var provider = Provider("drop-survive", new StringWriter());
        Reject(provider);
        var before = Rows("drop-survive");
        Assert.IsTrue(provider.CloseWithin(Long));
        CollectionAssert.AreEquivalent(before, Rows("drop-survive"));
        provider.CreateLogger("test").LogInformation("Too late");
        var after = Rows("drop-survive");
        Assert.AreEqual(1L, after["invalid"]);
        Assert.AreEqual(1L, after["closed"]);
        CollectionAssert.AreEquivalent(Expected(provider.Stats), after);
        foreach (var (reason, count) in before) Assert.IsGreaterThanOrEqualTo(count, after[reason]);
    }

    /// <summary>prometheus_text_format</summary>
    [TestMethod]
    public void PrometheusTextFormat()
    {
        var example = Metric().GetProperty("prometheus_text_example");
        var counts = example.GetProperty("counts").EnumerateArray()
            .Select(c => new LogDropCount(c.GetProperty("service").GetString()!, c.GetProperty("reason").GetString()!, c.GetProperty("count").GetInt64()))
            .ToList();
        Assert.AreEqual(example.GetProperty("text").GetString(), LogDropMetrics.PrometheusText(counts));

        using var provider = Provider("drop-prometheus", new StringWriter());
        Reject(provider);
        var live = LogDropMetrics.PrometheusText();
        StringAssert.Contains(live, "onenexus_log_records_dropped_total{service=\"drop-prometheus\",reason=\"invalid\"} 1\n");
        StringAssert.Contains(live, "onenexus_log_records_dropped_total{service=\"drop-prometheus\",reason=\"closed\"} 0\n");
    }

    /// <summary>otel_asynchronous_counter</summary>
    [TestMethod]
    public void OtelAsynchronousCounter()
    {
        using var provider = Provider("drop-otel", new StringWriter());
        Reject(provider);
        var instruments = new List<Instrument>();
        var observed = new List<(string? Service, string? Reason, long Count)>();
        using var listener = new MeterListener();
        listener.InstrumentPublished = (instrument, l) =>
        {
            if (instrument.Meter.Name != LogDropMetrics.MeterName) return;
            instruments.Add(instrument);
            l.EnableMeasurementEvents(instrument);
        };
        listener.SetMeasurementEventCallback<long>((_, value, tags, _) =>
        {
            var tagMap = tags.ToArray().ToDictionary(t => t.Key, t => t.Value as string);
            Assert.HasCount(2, tagMap);
            observed.Add((tagMap["service"], tagMap["reason"], value));
        });
        listener.Start();
        listener.RecordObservableInstruments();

        var instrument = instruments.Single();
        Assert.IsInstanceOfType<ObservableCounter<long>>(instrument);
        Assert.AreEqual(Metric().GetProperty("otel_name").GetString(), instrument.Name);
        Assert.AreEqual(Metric().GetProperty("otel_unit").GetString(), instrument.Unit);
        var snapshot = LogDropMetrics.Snapshot();
        // Other tests' services are process-wide too: compare this service exactly and the row count overall.
        Assert.HasCount(snapshot.Count, observed);
        CollectionAssert.AreEqual(
            snapshot.Where(row => row.Service == "drop-otel").Select(row => (row.Service, row.Reason, row.Count)).ToArray(),
            observed.Where(row => row.Service == "drop-otel").Select(row => (row.Service!, row.Reason!, row.Count)).ToArray());
        Assert.AreEqual(1L, observed.Single(row => row is { Service: "drop-otel", Reason: "invalid" }).Count);
    }

    /// <summary>Blocks every write until <see cref="Open"/> is set.</summary>
    private sealed class GateWriter : StringWriter
    {
        public ManualResetEventSlim Open { get; } = new();
        public override void WriteLine(string? value)
        {
            Open.Wait();
            base.WriteLine(value);
        }
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
}
