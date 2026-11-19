using System.Collections.Frozen;
using System.Text.RegularExpressions;

namespace OneNexus.Observability;

/// <summary>Request-local diagnostic attribution. Authentication remains the caller's responsibility.</summary>
public sealed class RequestLogContext : IDisposable
{
    internal static readonly FrozenSet<string> FieldNames = new[] {
        "principal_id", "tenant_id", "error_code", "request_event",
        "http.request.method", "http.route", "http.response.status_code", "duration_ms",
    }.ToFrozenSet(StringComparer.Ordinal);
    private static readonly Regex ErrorCode = new(@"\A[A-Za-z0-9._:-]{1,128}\z", RegexOptions.CultureInvariant);
    private static readonly Regex Tenant = new(@"\A[0-9a-f]{32}\z", RegexOptions.CultureInvariant);
    private static readonly Regex Principal = new(@"\Anx1://[A-Za-z0-9._:-]+/([0-9a-f]{32})/[A-Za-z0-9._:-]+/[A-Za-z0-9._:-]+/(User|ServiceClient|Workload)/[A-Za-z0-9._:-]+\z", RegexOptions.CultureInvariant);
    private static readonly AsyncLocal<RequestLogContext?> Current = new();
    private readonly object gate = new();
    private readonly RequestLogContext? previous;
    private readonly Dictionary<string, object?> values;
    private bool closed;

    private RequestLogContext()
    {
        values = new() { ["principal_id"] = null, ["tenant_id"] = null };
        previous = Current.Value;
        Current.Value = this;
    }

    public static RequestLogContext Begin() => new();

    /// <summary>Call after credential verification, before policy/quota decisions. Tenant uses lowercase UUID-N.</summary>
    public void BindVerifiedIdentity(string? principalId, string? tenantId)
    {
        var tenant = tenantId is not null && Tenant.IsMatch(tenantId) && tenantId != new string('0', 32) ? tenantId : null;
        var match = principalId is not null && principalId.Length <= 1024 ? Principal.Match(principalId) : null;
        var principal = match is { Success: true } && tenant is not null && match.Groups[1].Value == tenant ? principalId : null;
        lock (gate)
        {
            if (closed) return;
            values["principal_id"] = principal;
            values["tenant_id"] = tenant;
        }
    }

    public void SetError(string code)
    {
        if (!ErrorCode.IsMatch(code)) throw new ArgumentException("invalid_error_code", nameof(code));
        lock (gate) { if (!closed) values["error_code"] = code; }
    }

    public Dictionary<string, object?> Fields() { lock (gate) return new(values); }
    public static IReadOnlyDictionary<string, object?> CurrentFields() => Current.Value?.Fields() ?? new Dictionary<string, object?>();

    /// <summary>Supply the route template and observed status; null before headers, 200 for an interrupted 200 stream.</summary>
    public Dictionary<string, object?> TerminalFields(string method, string route, int? statusCode, double durationMs, bool interrupted = false)
    {
        var result = Fields();
        if (result.Count == 0) throw new InvalidOperationException("request_context_closed");
        result["request_event"] = interrupted ? "interrupted" : "completed";
        result["http.request.method"] = method;
        result["http.route"] = route;
        result["http.response.status_code"] = statusCode;
        result["duration_ms"] = durationMs;
        if (!result.ContainsKey("error_code")) result["error_code"] = statusCode >= 400 ? "UNCLASSIFIED" : null;
        return result;
    }

    /// <summary>Dispose at the HTTP boundary, in scope order, including failure/cancellation paths.</summary>
    public void Dispose()
    {
        lock (gate) { closed = true; values.Clear(); }
        if (ReferenceEquals(Current.Value, this)) Current.Value = previous;
    }
}
