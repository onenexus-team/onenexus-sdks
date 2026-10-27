using System.Collections.Frozen;
using System.Text.Json;
using OneNexus.LogContract;

namespace OneNexus.Observability;

public sealed class LogConfiguration
{
    public string Service { get; }
    public string Environment { get; }
    public string Region { get; }
    public FrozenSet<string> AllowedFields { get; }

    public LogConfiguration(string service, string environment, string region, IEnumerable<string>? allowedFields = null)
    {
        Service = service;
        Environment = environment;
        Region = region;
        AllowedFields = (allowedFields ?? []).ToFrozenSet(StringComparer.Ordinal);
        if (AllowedFields.Count > 32 || AllowedFields.Any(f => string.IsNullOrWhiteSpace(f) || f.Length > 128 || Contract.ReservedFields.Contains(f)))
            throw new ArgumentException("invalid_allowed_fields");
        var record = JsonSerializer.SerializeToElement(new { timestamp = 0, level = "INFO", service, environment, region, message = "Configuration" });
        if (Contract.Validate(record).Count != 0) throw new ArgumentException("invalid_log_configuration");
    }

    internal bool Equivalent(LogConfiguration other) => Service == other.Service && Environment == other.Environment &&
        Region == other.Region && AllowedFields.SetEquals(other.AllowedFields);
}
