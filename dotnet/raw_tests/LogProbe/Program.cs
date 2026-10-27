using System.Text.Json;
using Microsoft.Extensions.Logging;
using OneNexus.LogContract;
using OneNexus.Observability;

try
{
    if (args.Length == 1 && args[0] == "emit")
    {
        using var provider = new JsonLogProvider(new("dotnet-package-probe", "development", "region-1", ["attempt"]));
        var logger = provider.CreateLogger("probe");
        // Test input represents context received from an edge. The service API never generates it.
        var headers = new Dictionary<string, string> { ["traceparent"] = "00-11111111111111111111111111111111-2222222222222222-00" };
        for (var attempt = 1; attempt <= 2; attempt++)
            using (CorrelationContext.BindIncoming(headers, trusted: true))
                logger.LogInformation("Attempt {attempt}", attempt);
        using (CorrelationContext.BindIncoming([], trusted: true)) logger.LogInformation("Uncorrelated request");
        if (provider.DroppedRecords != 0 || CorrelationContext.TraceId is not null) throw new InvalidOperationException("probe_failed");
    }
    else if (args.Length == 6 && args[0] == "verify")
    {
        // Input: exported application log bodies, one JSON record per line, for one request.
        // Fail closed: explicit expected trace, environment, region and services; never silently skip rows.
        var path = args[1];
        var expectedTrace = args[2];
        var expectedEnvironment = args[3];
        var expectedRegion = args[4];
        var requiredServices = args[5].Split(',').ToHashSet(StringComparer.Ordinal);
        var observed = new HashSet<string>(StringComparer.Ordinal);
        var count = 0;
        if (new FileInfo(path).Length > 16 * 1024 * 1024) throw new InvalidOperationException("input_too_large");
        foreach (var line in File.ReadLines(path))
        {
            if (++count > 10000 || System.Text.Encoding.UTF8.GetByteCount(line) > Contract.MaxRecordBytes) throw new InvalidOperationException("input_limit_exceeded");
            using var document = JsonDocument.Parse(line, new JsonDocumentOptions { MaxDepth = 32 });
            var row = document.RootElement;
            var profile = row.TryGetProperty("event", out _) ? "lifecycle" : "correlated";
            if (Contract.Validate(row, profile).Count != 0 || row.GetProperty("trace_id").GetString() != expectedTrace ||
                row.GetProperty("environment").GetString() != expectedEnvironment || row.GetProperty("region").GetString() != expectedRegion)
                throw new InvalidOperationException("log_validation_failed");
            observed.Add(row.GetProperty("service").GetString()!);
        }
        if (count == 0 || !requiredServices.IsSubsetOf(observed)) throw new InvalidOperationException("required_service_missing");
        Console.WriteLine($"PASS: {count} records; required services present; contract {Contract.Version} ({Contract.Digest})");
    }
    else
    {
        Console.Error.WriteLine("Usage: LogProbe emit | verify logs.ndjson trace_id environment region service1,service2");
        return 2;
    }
    return 0;
}
catch (Exception)
{
    Console.Error.WriteLine("FAIL: log validation or input failed; no input values are printed.");
    return 1;
}
