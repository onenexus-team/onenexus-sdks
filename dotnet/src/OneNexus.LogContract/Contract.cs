using System.Collections.Frozen;
using System.Security.Cryptography;
using System.Text;
using System.Text.Encodings.Web;
using System.Text.Json;
using System.Text.Json.Nodes;
using Corvus.Json;
using OneNexus.LogContract.Generated;

namespace OneNexus.LogContract;

/// <summary>The generated package reads the canonical contract; no runtime download.</summary>
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
    public static FrozenSet<string> ReservedFields { get; }

    static Contract()
    {
        JsonOptions.MakeReadOnly(populateMissingResolver: true);
        using var manifest = JsonDocument.Parse(ReadResource("manifest.json"));
        var root = manifest.RootElement;
        Version = root.GetProperty("version").GetString()!;
        Digest = root.GetProperty("sha256").GetString()!;
        using var hash = IncrementalHash.CreateHash(HashAlgorithmName.SHA256);
        foreach (var file in root.GetProperty("files").EnumerateArray())
        {
            var name = file.GetProperty("path").GetString()!;
            var data = ReadResource(name);
            if (Convert.ToHexStringLower(SHA256.HashData(data)) != file.GetProperty("sha256").GetString())
                throw new InvalidOperationException("contract_artifact_hash_mismatch");
            hash.AppendData(Encoding.UTF8.GetBytes(name + "\0"));
            hash.AppendData(data);
        }
        if (Convert.ToHexStringLower(hash.GetHashAndReset()) != Digest)
            throw new InvalidOperationException("contract_digest_mismatch");
        using var schema = JsonDocument.Parse(ReadResource("schema.json"));
        if (schema.RootElement.GetProperty("x-contract-version").GetString() != Version)
            throw new InvalidOperationException("contract_version_mismatch");
        var limits = schema.RootElement.GetProperty("x-semantic-checks");
        MaxMessageBytes = limits.GetProperty("message_max_utf8_bytes").GetInt32();
        MaxRecordBytes = limits.GetProperty("record_max_compact_utf8_bytes").GetInt32();
        ReservedFields = schema.RootElement.GetProperty("$defs").GetProperty("common")
            .GetProperty("properties").EnumerateObject().Select(p => p.Name).ToFrozenSet(StringComparer.Ordinal);
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
        if (profile is not ("common" or "correlated" or "lifecycle")) return ["unknown_profile"];
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
            else if (profile != "common")
            {
                errors.Add("missing_or_invalid_trace_id");
                corrected["trace_id"] = "11111111111111111111111111111111";
            }
            var normalized = JsonSerializer.SerializeToElement(corrected, JsonOptions);
            var valid = profile switch
            {
                "common" => new CommonRecord(normalized).Validate(ValidationContext.ValidContext).IsValid,
                "correlated" => new CorrelatedRecord(normalized).Validate(ValidationContext.ValidContext).IsValid,
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
