using System.Text.Json;
using Microsoft.VisualStudio.TestTools.UnitTesting;
using OneNexus.Observability.Rules;

namespace OneNexus.Observability.Tests;

[TestClass]
public sealed class ContractTests
{
    [TestMethod]
    public void AllSharedCasesThroughActualPackageApis()
    {
        using var vectors = JsonDocument.Parse(File.ReadAllBytes(Environment.GetEnvironmentVariable("ONENEXUS_LOGGING_SCENARIOS") ?? throw new InvalidOperationException("Set ONENEXUS_LOGGING_SCENARIOS to shared scenarios.json")));
        var observations = new List<Dictionary<string, object?>>();
        foreach (var test in vectors.RootElement.GetProperty("record_cases").EnumerateArray())
        {
            var actual = Contract.Validate(test.GetProperty("record"), test.GetProperty("profile").GetString()!);
            observations.Add(new() { ["kind"] = "record", ["id"] = test.GetProperty("id").GetString(), ["errors"] = actual });
        }
        foreach (var test in vectors.RootElement.GetProperty("context_cases").EnumerateArray())
        {
            Dictionary<string, object?> observed;
            using (CorrelationContext.BindAtEdge([new("traceparent", test.GetProperty("traceparent").GetString()!)], test.GetProperty("trusted").GetBoolean()))
                observed = new()
                {
                    ["kind"] = "context",
                    ["id"] = test.GetProperty("id").GetString(),
                    ["trace_id"] = CorrelationContext.TraceId,
                    ["outgoing_traceparent"] = CorrelationContext.OutgoingHeaders()["traceparent"]
                };
            observed["after_trace_id"] = CorrelationContext.TraceId;
            observations.Add(observed);
        }
        var envelope = new { adapter_protocol = 1, contract_version = Contract.Version, contract_sha256 = Contract.Digest, results = observations };
        var path = Environment.GetEnvironmentVariable("ONENEXUS_LOGGING_RESULTS") ?? Path.Combine(AppContext.BaseDirectory, "contract-results.json");
        File.WriteAllText(path, JsonSerializer.Serialize(envelope, Contract.JsonOptions));
        Assert.HasCount(66, observations);
    }

    [TestMethod]
    public void StableCodesForAdditionalMalformedInputs()
    {
        Assert.HasCount(1, Contract.Validate(JsonSerializer.SerializeToElement(new { }), "unknown"));
        Assert.AreEqual("unknown_profile", Contract.Validate(JsonSerializer.SerializeToElement(new { }), "unknown")[0]);
        Assert.AreEqual("schema_invalid", Contract.Validate(JsonSerializer.SerializeToElement(42))[0]);
        Assert.ThrowsExactly<ArgumentException>(() => Contract.ReadResource("missing"));
    }
}
