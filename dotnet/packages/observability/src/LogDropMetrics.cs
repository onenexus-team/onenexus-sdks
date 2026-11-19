using System.Collections.Concurrent;
using System.Diagnostics.Metrics;
using System.Globalization;
using System.Text;

namespace OneNexus.Observability;

/// <summary>One row of the drop metric: lines a service's providers did not write for one reason.</summary>
public readonly record struct LogDropCount(string Service, string Reason, long Count);

/// <summary>Why a line was not written. The order matches <see cref="LogDropMetrics.ReasonNames"/>.</summary>
internal enum DropReason { Closed, Invalid, IoErrors, QueueFull }

/// <summary>
/// One process-wide drop metric per (service, reason) (design review R1; tests/logging/scenarios.json drop_metric).
/// Providers of one service are summed; counts never decrease, also after dispose. Read it as a
/// <see cref="Snapshot"/>, as <see cref="PrometheusText"/>, or by adding the <see cref="MeterName"/> meter to the
/// host's OpenTelemetry metrics (an asynchronous counter named <see cref="InstrumentName"/>).
/// </summary>
public static class LogDropMetrics
{
    public const string MeterName = "OneNexus.Observability";
    public const string InstrumentName = "onenexus.log.records.dropped";
    public const string Unit = "{record}";
    public const string Description = "Log records the logging SDK did not write, by reason.";
    public const string PrometheusName = "onenexus_log_records_dropped_total";
    public const string ServiceLabel = "service";
    public const string ReasonLabel = "reason";

    /// <summary>The spec's reason strings, indexed by <see cref="DropReason"/>.</summary>
    public static IReadOnlyList<string> ReasonNames { get; } = ["closed", "invalid", "io_errors", "queue_full"];

    private static readonly ConcurrentDictionary<string, ServiceDrops> Services = new(StringComparer.Ordinal);
    private static readonly Meter Meter = new(MeterName);
    // Kept alive by the meter; created with the class so a host that adds the meter always sees it.
    private static readonly ObservableCounter<long> Instrument = Meter.CreateObservableCounter(InstrumentName, Observe, Unit, Description);

    /// <summary>Every (service, reason) row, sorted by service then reason (ordinal).</summary>
    public static IReadOnlyList<LogDropCount> Snapshot() =>
        Services.SelectMany(service => ReasonNames.Select((reason, index) => new LogDropCount(service.Key, reason, service.Value.Read(index))))
            .OrderBy(row => row.Service, StringComparer.Ordinal).ThenBy(row => row.Reason, StringComparer.Ordinal).ToList();

    /// <summary>Prometheus text exposition of <paramref name="counts"/> (default: the current snapshot), for a /metrics route.</summary>
    public static string PrometheusText(IReadOnlyList<LogDropCount>? counts = null)
    {
        var text = new StringBuilder()
            .Append("# HELP ").Append(PrometheusName).Append(' ').Append(Description).Append('\n')
            .Append("# TYPE ").Append(PrometheusName).Append(" counter\n");
        foreach (var row in (counts ?? Snapshot()).OrderBy(row => row.Service, StringComparer.Ordinal).ThenBy(row => row.Reason, StringComparer.Ordinal))
            text.Append(PrometheusName)
                .Append('{').Append(ServiceLabel).Append("=\"").Append(Escape(row.Service))
                .Append("\",").Append(ReasonLabel).Append("=\"").Append(Escape(row.Reason)).Append("\"} ")
                .Append(row.Count.ToString(CultureInfo.InvariantCulture)).Append('\n');
        return text.ToString();
    }

    /// <summary>The counters of <paramref name="service"/>, every reason present at 0 from the first provider.</summary>
    internal static ServiceDrops Register(string service) => Services.GetOrAdd(service, _ => new ServiceDrops());

    private static IEnumerable<Measurement<long>> Observe() => Snapshot().Select(row =>
        new Measurement<long>(row.Count, new KeyValuePair<string, object?>(ServiceLabel, row.Service), new KeyValuePair<string, object?>(ReasonLabel, row.Reason)));

    private static string Escape(string value) => value.Replace("\\", "\\\\").Replace("\"", "\\\"").Replace("\n", "\\n");

    /// <summary>One service's drop counters, shared by all its providers.</summary>
    internal sealed class ServiceDrops
    {
        private readonly long[] counts = new long[ReasonNames.Count];
        public void Add(DropReason reason) => Interlocked.Increment(ref counts[(int)reason]);
        public long Read(int index) => Interlocked.Read(ref counts[index]);
    }
}
