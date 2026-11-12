using System.Reflection;
using System.Text.Json;
using Microsoft.Extensions.Logging;
using Microsoft.VisualStudio.TestTools.UnitTesting;
using OneNexus.Observability.Rules;

namespace OneNexus.Observability.Tests;

/// <summary>One field registry (design review E1; tests/logging/scenarios.json field_registry). One data row per case id.</summary>
[TestClass]
public sealed class FieldRegistryTests
{
    private static JsonElement Spec()
    {
        using var suite = JsonDocument.Parse(File.ReadAllBytes(Environment.GetEnvironmentVariable("ONENEXUS_LOGGING_SCENARIOS")!));
        return suite.RootElement.GetProperty("field_registry").Clone();
    }

    private static JsonElement Case(string group, string id) =>
        Spec().GetProperty(group).EnumerateArray().Single(c => c.GetProperty("id").GetString() == id);

    /// <summary>names is a list, {prefix, count} or {prefix, repeat, count} (names_expansion).</summary>
    private static string[] Names(JsonElement names)
    {
        if (names.ValueKind == JsonValueKind.Array) return names.EnumerateArray().Select(n => n.GetString()!).ToArray();
        var prefix = names.GetProperty("prefix").GetString()!;
        var count = names.GetProperty("count").GetInt32();
        return names.TryGetProperty("repeat", out var repeat)
            ? [prefix + string.Concat(Enumerable.Repeat(repeat.GetString()!, count))]
            : Enumerable.Range(0, count).Select(i => prefix + i).ToArray();
    }

    private static object? Value(JsonElement value) => value.ValueKind switch
    {
        JsonValueKind.String => value.GetString(),
        JsonValueKind.Number => value.TryGetInt64(out var whole) ? whole : value.GetDouble(),
        JsonValueKind.True or JsonValueKind.False => value.GetBoolean(),
        JsonValueKind.Null => null,
        JsonValueKind.Object => value.EnumerateObject().ToDictionary(p => p.Name, p => Value(p.Value)),
        _ => value.EnumerateArray().Select(Value).ToList(),
    };

    [TestMethod]
    [DataRow("accepts_service_namespace")]
    [DataRow("accepts_registered_field")]
    [DataRow("accepts_otel_namespace")]
    [DataRow("accepts_registered_in_reserved")]
    [DataRow("accepts_max_custom_fields")]
    [DataRow("rejects_protected")]
    [DataRow("rejects_bad_format")]
    [DataRow("rejects_too_many_segments")]
    [DataRow("rejects_too_long")]
    [DataRow("rejects_reserved_namespace")]
    [DataRow("rejects_unregistered_flat")]
    [DataRow("rejects_unregistered_namespace")]
    [DataRow("rejects_too_many")]
    public void ConfigCase(string id)
    {
        var item = Case("config_cases", id);
        var names = Names(item.GetProperty("names"));
        if (item.GetProperty("accepted").GetBoolean())
        {
            Assert.HasCount(names.Length, new LogConfiguration("registry-test", "development", "region-1", names).AllowedFields, id);
            return;
        }
        var error = Assert.ThrowsExactly<ArgumentException>(() => new LogConfiguration("registry-test", "development", "region-1", names));
        var code = Spec().GetProperty("config_error").GetString();
        Assert.StartsWith($"{code}: {item.GetProperty("reason").GetString()}: ", error.Message, id);
    }

    [TestMethod]
    [DataRow("scalar_values_kept")]
    [DataRow("object_value_removed")]
    [DataRow("array_value_removed")]
    [DataRow("registered_type_enforced")]
    [DataRow("registered_type_accepted")]
    public void ValueCase(string id)
    {
        var item = Case("value_cases", id);
        var allowed = Spec().GetProperty("value_allowed_fields").EnumerateArray().Select(f => f.GetString()!).ToArray();
        var fields = item.GetProperty("fields").EnumerateObject().ToDictionary(p => p.Name, p => Value(p.Value));
        using var output = new StringWriter();
        using var provider = new JsonLogProvider(new("registry-test", "development", "region-1", allowed), output);
        provider.CreateLogger("test").Log(LogLevel.Information, default, fields, null, (_, _) => "Field values");
        Assert.IsTrue(provider.CloseWithin(TimeSpan.FromSeconds(10)));
        Assert.AreEqual(0L, provider.DroppedRecords, id); // The line is kept.
        var row = JsonDocument.Parse(output.ToString()).RootElement;
        CollectionAssert.AreEqual(item.GetProperty("kept").EnumerateArray().Select(k => k.GetString()).ToArray(),
            fields.Keys.Where(k => row.TryGetProperty(k, out _)).Order(StringComparer.Ordinal).ToArray(), id);
        var dropped = item.GetProperty("dropped_field_count");
        if (dropped.ValueKind == JsonValueKind.Null) Assert.IsFalse(row.TryGetProperty("logging.dropped_field_count", out _), id);
        else Assert.AreEqual(dropped.GetInt32(), row.GetProperty("logging.dropped_field_count").GetInt32(), id);
        Assert.IsEmpty(Contract.Validate(row), id);
    }

    [TestMethod]
    public void EveryDotnetCaseHasADataRow()
    {
        var rows = new[] { nameof(ConfigCase), nameof(ValueCase) }
            .SelectMany(m => typeof(FieldRegistryTests).GetMethod(m)!.GetCustomAttributes<DataRowAttribute>())
            .Select(r => (string)r.Data[0]!).Order(StringComparer.Ordinal).ToArray();
        var spec = Spec();
        var cases = spec.GetProperty("config_cases").EnumerateArray().Concat(spec.GetProperty("value_cases").EnumerateArray())
            .Where(c => c.GetProperty("languages").EnumerateArray().Any(l => l.GetString() == "dotnet"))
            .Select(c => c.GetProperty("id").GetString()!).Order(StringComparer.Ordinal).ToArray();
        CollectionAssert.AreEqual(cases, rows);
    }

    [TestMethod]
    public void LimitsComeFromTheSchema()
    {
        using var schema = JsonDocument.Parse(Contract.ReadResource("schema.json"));
        Assert.AreEqual(schema.RootElement.GetProperty("x-field-registry").GetProperty("max_custom_fields").GetInt32(), Contract.MaxCustomFields);
    }

    [TestMethod]
    public void TrailingNewlineIsNotAValidName()
    {
        var error = Assert.ThrowsExactly<ArgumentException>(() => Contract.CheckAllowedFields(["example.a\n"]));
        Assert.AreEqual("invalid_allowed_fields: format: example.a\n", error.Message);
    }
}
