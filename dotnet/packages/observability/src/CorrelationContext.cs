using System.Diagnostics;
using System.Text.RegularExpressions;

namespace OneNexus.Observability;

/// <summary>Execution-local W3C context. Does not create recording spans or install exporters.</summary>
public static partial class CorrelationContext
{
    private sealed record Frame(ActivityContext? Context, Frame? Parent);
    private static readonly AsyncLocal<Frame?> Current = new();

    [GeneratedRegex("^00-[0-9a-f]{32}-[0-9a-f]{16}-[0-9a-f]{2}$", RegexOptions.CultureInvariant)]
    private static partial Regex TraceparentPattern();

    /// <summary>Restore only trusted context. Missing, duplicate or invalid input remains uncorrelated.</summary>
    public static IDisposable BindIncoming(IEnumerable<KeyValuePair<string, string>> headers, bool trusted, bool preserveSampling = true)
        => Bind(Parse(headers, trusted, preserveSampling));

    /// <summary>Explicit edge-only policy used by the cross-language contract; services must use BindIncoming.</summary>
    public static IDisposable BindAtEdge(IEnumerable<KeyValuePair<string, string>> headers, bool trusted, bool preserveSampling = false)
        => Bind(Parse(headers, trusted, preserveSampling) ?? new ActivityContext(ActivityTraceId.CreateRandom(), ActivitySpanId.CreateRandom(), ActivityTraceFlags.None));

    /// <summary>Suppress inherited context for independent system work.</summary>
    public static IDisposable BindUncorrelated() => Bind(null);

    public static string? TraceId => Active?.TraceId.ToHexString();

    public static IReadOnlyDictionary<string, string> OutgoingHeaders()
    {
        if (Active is not { } context) return new Dictionary<string, string>();
        return new Dictionary<string, string>
        {
            ["traceparent"] = $"00-{context.TraceId}-{context.SpanId}-{(context.TraceFlags.HasFlag(ActivityTraceFlags.Recorded) ? "01" : "00")}",
        };
    }

    private static ActivityContext? Active
    {
        get
        {
            var activity = Activity.Current;
            if (Current.Value is { } frame)
            {
                // Never replace the trusted boundary ID with an unrelated framework-created Activity.
                if (frame.Context is not { } bound) return null;
                return activity?.IdFormat == ActivityIdFormat.W3C && activity.TraceId == bound.TraceId
                    ? activity.Context : bound;
            }
            return activity?.IdFormat == ActivityIdFormat.W3C ? activity.Context : null;
        }
    }

    private static ActivityContext? Parse(IEnumerable<KeyValuePair<string, string>> headers, bool trusted, bool preserveSampling)
    {
        if (!trusted) return null;
        var candidates = headers.Where(h => h.Key.Equals("traceparent", StringComparison.OrdinalIgnoreCase)).Take(2).ToArray();
        if (candidates.Length != 1 || candidates[0].Value is not { Length: 55 } value ||
            !TraceparentPattern().IsMatch(value) || !ActivityContext.TryParse(value, null, true, out var context) ||
            context.TraceId == default || context.SpanId == default) return null;
        return new ActivityContext(context.TraceId, context.SpanId,
            preserveSampling ? context.TraceFlags : ActivityTraceFlags.None, traceState: null, isRemote: true);
    }

    private static IDisposable Bind(ActivityContext? context)
    {
        var frame = new Frame(context, Current.Value);
        Current.Value = frame;
        return new Scope(frame);
    }

    private sealed class Scope(Frame frame) : IDisposable
    {
        private bool disposed;
        public void Dispose()
        {
            if (disposed) return;
            if (!ReferenceEquals(Current.Value, frame)) throw new InvalidOperationException("correlation_scopes_must_exit_in_order");
            Current.Value = frame.Parent;
            disposed = true;
        }
    }
}
