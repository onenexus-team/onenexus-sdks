using System.Collections.Frozen;
using System.Text;
using System.Text.Encodings.Web;
using System.Text.Json;
using System.Text.Json.Nodes;
using System.Text.RegularExpressions;
using Corvus.Json;
using OneNexus.Observability.Rules.Generated;

namespace OneNexus.Observability.Rules;

/// <summary>Validation rules shipped in the logging assembly; no external contract package.</summary>
public static class Contract
{
    public static readonly JsonSerializerOptions JsonOptions = new()
    {
        Encoder = JavaScriptEncoder.UnsafeRelaxedJsonEscaping,
        MaxDepth = 32,
    };
    private static readonly UTF8Encoding StrictUtf8 = new(false, true);
    public static string Version { get; }
    public static string Digest { get; }
    public static int MaxMessageBytes { get; }
    public static int MaxRecordBytes { get; }
    public static int MaxFieldBytes { get; }
    public static int MaxStacktraceBytes { get; }
    public static int MaxDroppedFieldCount { get; }
    public static int MaxErrorTypeChars { get; }
    public static FrozenSet<string> ReservedFields { get; }
    /// <summary>The most custom field names one logger may allow (field registry <c>max_custom_fields</c>).</summary>
    public static int MaxCustomFields { get; }
    private static readonly Regex FieldNamePattern;
    private static readonly int FieldNameMaxChars;
    private static readonly FrozenDictionary<string, FieldValueType> RegisteredFields;
    private static readonly FrozenSet<string> FieldNamespaces;
    private static readonly FrozenSet<string> ReservedNamespaces;

    /// <summary>The value types of the field registry (<c>value_types</c>).</summary>
    private enum FieldValueType { String, Integer, Number, Boolean, Null }

    static Contract()
    {
        JsonOptions.MakeReadOnly(populateMissingResolver: true);
        Version = "0.6.0"; // Log-format identity; package version follows SDK.
        Digest = "b0703638c41630885ad82f6db201a84e04545912bd4aaf1035e995e08aeda40b"; // sha256 of the bundled schema.json
        using var schema = JsonDocument.Parse(ReadResource("schema.json"));
        var limits = schema.RootElement.GetProperty("x-semantic-checks");
        MaxMessageBytes = limits.GetProperty("message_max_utf8_bytes").GetInt32();
        MaxRecordBytes = limits.GetProperty("record_max_compact_utf8_bytes").GetInt32();
        MaxFieldBytes = limits.GetProperty("field_max_utf8_bytes").GetInt32();
        MaxStacktraceBytes = limits.GetProperty("stacktrace_max_utf8_bytes").GetInt32();
        var common = schema.RootElement.GetProperty("$defs").GetProperty("common").GetProperty("properties");
        MaxDroppedFieldCount = common.GetProperty("logging.dropped_field_count").GetProperty("maximum").GetInt32();
        MaxErrorTypeChars = common.GetProperty("error.type").GetProperty("maxLength").GetInt32();
        // Preserve logger-owned fields independently of optional shared properties.
        ReservedFields = schema.RootElement.GetProperty("x-protected-fields")
            .EnumerateArray().Select(p => p.GetString()!).ToFrozenSet(StringComparer.Ordinal);
        var registry = schema.RootElement.GetProperty("x-field-registry");
        MaxCustomFields = registry.GetProperty("max_custom_fields").GetInt32();
        FieldNamePattern = new Regex(registry.GetProperty("name_pattern").GetString()!, RegexOptions.CultureInvariant);
        FieldNameMaxChars = registry.GetProperty("name_max_chars").GetInt32();
        RegisteredFields = registry.GetProperty("fields").EnumerateObject()
            .ToFrozenDictionary(f => f.Name, f => ValueType(f.Value.GetProperty("type").GetString()!), StringComparer.Ordinal);
        FieldNamespaces = registry.GetProperty("namespaces").EnumerateObject().Select(n => n.Name).ToFrozenSet(StringComparer.Ordinal);
        ReservedNamespaces = registry.GetProperty("reserved_namespaces").EnumerateObject().Select(n => n.Name).ToFrozenSet(StringComparer.Ordinal);
    }

    private static FieldValueType ValueType(string name) => name switch
    {
        "string" => FieldValueType.String, "integer" => FieldValueType.Integer, "number" => FieldValueType.Number,
        "boolean" => FieldValueType.Boolean, "null" => FieldValueType.Null,
        _ => throw new InvalidOperationException("unknown_field_value_type"),
    };

    /// <summary>
    /// Check the custom field names a logger allows against the field registry (design review E1). Rules, in order:
    /// protected, format, registered field (accepted), reserved namespace, namespace; more than
    /// <see cref="MaxCustomFields"/> names is <c>too_many</c>. Throws
    /// <c>ArgumentException("invalid_allowed_fields: &lt;rule&gt;: &lt;detail&gt;")</c> for the first failure.
    /// </summary>
    public static void CheckAllowedFields(IReadOnlyCollection<string> names)
    {
        if (names.Count > MaxCustomFields) throw FieldError("too_many", $"{names.Count} > {MaxCustomFields}");
        foreach (var name in names)
        {
            if (ReservedFields.Contains(name)) throw FieldError("protected", name);
            // Match the whole name: '$' alone also matches before a final newline.
            if (name.Length > FieldNameMaxChars || FieldNamePattern.Match(name) is not { Success: true } match || match.Length != name.Length)
                throw FieldError("format", name);
            if (RegisteredFields.ContainsKey(name)) continue;
            var dot = name.IndexOf('.');
            var head = dot < 0 ? name : name[..dot];
            if (ReservedNamespaces.Contains(head)) throw FieldError("reserved", name);
            if (dot < 0 || !FieldNamespaces.Contains(head)) throw FieldError("namespace", name);
        }
    }

    private static ArgumentException FieldError(string rule, string detail) => new($"invalid_allowed_fields: {rule}: {detail}");

    /// <summary>A flat scalar (string, finite number, boolean or null) of the field's registered type, if it has one.</summary>
    internal static bool ValidFieldValue(string name, JsonElement value)
    {
        if (value.ValueKind is JsonValueKind.Null) return true;
        if (value.ValueKind is JsonValueKind.Object or JsonValueKind.Array) return false;
        if (!RegisteredFields.TryGetValue(name, out var type)) return true;
        return type switch
        {
            FieldValueType.String => value.ValueKind is JsonValueKind.String,
            FieldValueType.Integer => value.ValueKind is JsonValueKind.Number && double.IsInteger(value.GetDouble()),
            FieldValueType.Number => value.ValueKind is JsonValueKind.Number,
            FieldValueType.Boolean => value.ValueKind is JsonValueKind.True or JsonValueKind.False,
            _ => false, // Null: only null, accepted above.
        };
    }

    public static byte[] ReadResource(string name)
    {
        using var stream = typeof(Contract).Assembly.GetManifestResourceStream("Contract." + name)
            ?? throw new ArgumentException("unknown_contract_resource", nameof(name));
        using var bytes = new MemoryStream();
        stream.CopyTo(bytes);
        return bytes.ToArray();
    }

    /// <summary>Stable codes only, never input values or schema error payloads.</summary>
    public static IReadOnlyList<string> Validate(JsonElement record, string profile = "common")
    {
        if (profile is not ("common" or "correlated" or "lifecycle" or "request")) return ["unknown_profile"];
        var errors = new SortedSet<string>(StringComparer.Ordinal);
        if (record.ValueKind != JsonValueKind.Object) return ["schema_invalid"];
        try
        {
            var corrected = JsonNode.Parse(record.GetRawText())!.AsObject();
            if (!record.TryGetProperty("message", out var message) ||
                !new MessageValue(message).Validate(ValidationContext.ValidContext).IsValid)
            {
                errors.Add("missing_or_invalid_message");
                corrected["message"] = "valid";
            }
            if (record.TryGetProperty("trace_id", out var trace))
            {
                if (!new TraceValue(trace).Validate(ValidationContext.ValidContext).IsValid)
                {
                    errors.Add("missing_or_invalid_trace_id");
                    corrected["trace_id"] = "11111111111111111111111111111111";
                }
            }
            else if (profile is "correlated" or "lifecycle")
            {
                errors.Add("missing_or_invalid_trace_id");
                corrected["trace_id"] = "11111111111111111111111111111111";
            }
            var normalized = JsonSerializer.SerializeToElement(corrected, JsonOptions);
            var valid = profile switch
            {
                "common" => new CommonRecord(normalized).Validate(ValidationContext.ValidContext).IsValid,
                "correlated" => new CorrelatedRecord(normalized).Validate(ValidationContext.ValidContext).IsValid,
                "request" => new RequestRecord(normalized).Validate(ValidationContext.ValidContext).IsValid,
                _ => new LifecycleRecord(normalized).Validate(ValidationContext.ValidContext).IsValid,
            };
            if (!valid || !record.TryGetProperty("timestamp", out var timestamp) || timestamp.ValueKind != JsonValueKind.Number || !timestamp.TryGetInt64(out _))
                errors.Add("schema_invalid");
            if (message.ValueKind == JsonValueKind.String && StrictUtf8.GetByteCount(message.GetString()!) > MaxMessageBytes)
                errors.Add("missing_or_invalid_message");
            if (CompactBytes(record) > MaxRecordBytes) errors.Add("record_too_large");
        }
        catch (Exception ex) when (ex is ArgumentException or InvalidOperationException or JsonException)
        {
            errors.Add("invalid_json_record");
        }
        return errors.ToArray();
    }

    // The contract counts compact UTF-8, not System.Text.Json's optional Unicode escapes.
    private static long CompactBytes(JsonElement value) => value.ValueKind switch
    {
        JsonValueKind.Object => 2 + value.EnumerateObject().Sum(p => StringBytes(p.Name) + 1 + CompactBytes(p.Value)) + Math.Max(0, value.EnumerateObject().Count() - 1),
        JsonValueKind.Array => 2 + value.EnumerateArray().Sum(CompactBytes) + Math.Max(0, value.GetArrayLength() - 1),
        JsonValueKind.String => StringBytes(value.GetString()!),
        _ => value.GetRawText().Length,
    };

    private static long StringBytes(string text)
    {
        long count = 2 + StrictUtf8.GetByteCount(text);
        foreach (char c in text)
            count += c switch { '"' or '\\' or '\b' or '\f' or '\n' or '\r' or '\t' => 1, < ' ' => 5, _ => 0 };
        return count;
    }
}
