using System;
using System.Collections.Generic;
using System.Linq;
using System.Net;
using System.Net.Http;
using System.Net.Http.Json;
using System.Text.Json;
using System.Text.Json.Serialization;
using System.Threading;
using System.Threading.Tasks;

namespace OneNexus.Sdk.Core;

/// <summary>A Problem Details response from any OneNexus service. Use ProblemType to distinguish failures sharing an HTTP status.</summary>
public sealed class PlatformException : HttpRequestException
{
    private PlatformException(HttpStatusCode status, Problem problem, string? requestId, string? traceId)
        : base(problem.Detail ?? problem.Title ?? $"HTTP {(int)status}", null, status)
    {
        ProblemType = problem.Type;
        Title = problem.Title;
        Detail = problem.Detail;
        Instance = problem.Instance;
        Code = problem.Code ?? CodeFromType(problem.Type);
        RequestId = problem.RequestId ?? requestId;
        TraceId = problem.TraceId ?? problem.SnakeCaseTraceId ?? traceId;
        FieldErrors = ReadFieldErrors(problem.Errors);
    }

    /// <summary>RFC 9457 problem type URI.</summary>
    public string? ProblemType { get; }

    /// <summary>Summary supplied by the service.</summary>
    public string? Title { get; }

    /// <summary>Explanation of this occurrence.</summary>
    public string? Detail { get; }

    /// <summary>URI identifying this occurrence.</summary>
    public string? Instance { get; }

    /// <summary>Platform classification such as failed_precondition, when known.</summary>
    public string? Code { get; }

    /// <summary>Request identifier from the problem body or the X-Request-ID response header, when present.</summary>
    public string? RequestId { get; }

    /// <summary>Distributed trace identifier from the problem body or the X-Trace-Id response header, when present.</summary>
    public string? TraceId { get; }

    /// <summary>Validation messages grouped by field. A message that applies to no single field uses an empty key.</summary>
    public IReadOnlyDictionary<string, string[]> FieldErrors { get; }

    internal static async Task ThrowIfFailedAsync(HttpResponseMessage response, CancellationToken cancellationToken)
    {
        if (response.IsSuccessStatusCode)
        {
            return;
        }

        if (response.Content.Headers.ContentType?.MediaType is string mediaType &&
            (mediaType.Equals("application/problem+json", StringComparison.OrdinalIgnoreCase) ||
             mediaType.Equals("application/json", StringComparison.OrdinalIgnoreCase)))
        {
            Problem? problem;
            try
            {
                problem = await response.Content.ReadFromJsonAsync(SdkJsonContext.Default.Problem, cancellationToken).ConfigureAwait(false);
            }
            catch (JsonException)
            {
                problem = null;
            }
            if (problem is not null && (problem.Type ?? problem.Title ?? problem.Detail ?? problem.Code) is not null)
            {
                throw new PlatformException(response.StatusCode, problem, Header(response, "X-Request-ID"), Header(response, "X-Trace-Id"));
            }
        }

        response.EnsureSuccessStatusCode();
    }

    private static string? Header(HttpResponseMessage response, string name) =>
        response.Headers.TryGetValues(name, out IEnumerable<string>? values) ? values.FirstOrDefault() : null;

    private static string? CodeFromType(string? type)
    {
        const string prefix = "https://onenexus.cloud/errors/";
        return type?.StartsWith(prefix, StringComparison.Ordinal) == true ? type[prefix.Length..].Replace('-', '_') : null;
    }

    // CAS sends {"field": ["message", ...]}; MLOps sends [{"field": ..., "code": ..., "message": ...}, ...].
    // Entries in any other shape are skipped so the rest of the problem still reaches the caller.
    private static Dictionary<string, string[]> ReadFieldErrors(JsonElement? errors)
    {
        var messages = new List<KeyValuePair<string, string>>();
        if (errors is { ValueKind: JsonValueKind.Object } byField)
        {
            foreach (JsonProperty field in byField.EnumerateObject())
            {
                if (field.Value.ValueKind == JsonValueKind.Array)
                {
                    messages.AddRange(field.Value.EnumerateArray().Where(IsString).Select(message => Message(field.Name, message)));
                }
                else if (IsString(field.Value))
                {
                    messages.Add(Message(field.Name, field.Value));
                }
            }
        }
        else if (errors is { ValueKind: JsonValueKind.Array } list)
        {
            foreach (JsonElement error in list.EnumerateArray())
            {
                if (error.ValueKind == JsonValueKind.Object && error.TryGetProperty("message", out JsonElement message) && IsString(message))
                {
                    var field = error.TryGetProperty("field", out JsonElement name) && IsString(name) ? name.GetString()! : "";
                    messages.Add(Message(field, message));
                }
            }
        }
        return messages.GroupBy(message => message.Key, StringComparer.Ordinal)
            .ToDictionary(group => group.Key, group => group.Select(message => message.Value).ToArray(), StringComparer.Ordinal);

        static bool IsString(JsonElement value) => value.ValueKind == JsonValueKind.String;
        static KeyValuePair<string, string> Message(string field, JsonElement message) => new KeyValuePair<string, string>(field, message.GetString()!);
    }

    internal sealed class Problem
    {
        public string? Type { get; init; }
        public string? Title { get; init; }
        public string? Detail { get; init; }
        public string? Instance { get; init; }
        public string? Code { get; init; }
        public string? RequestId { get; init; }
        public string? TraceId { get; init; }

        [JsonPropertyName("trace_id")]
        public string? SnakeCaseTraceId { get; init; }

        public JsonElement? Errors { get; init; }
    }
}
