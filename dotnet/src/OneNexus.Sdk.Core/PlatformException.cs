using System;
using System.Collections.Generic;
using System.Net;
using System.Net.Http;
using System.Net.Http.Json;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;

namespace OneNexus.Sdk.Core;

/// <summary>A CAS Problem Details response. Use ProblemType to distinguish failures sharing an HTTP status.</summary>
public sealed class PlatformException : HttpRequestException
{
    private PlatformException(HttpStatusCode status, Problem problem)
        : base(problem.Detail ?? problem.Title ?? $"HTTP {(int)status}", null, status)
    {
        ProblemType = problem.Type;
        Title = problem.Title;
        Detail = problem.Detail;
        Instance = problem.Instance;
        Code = problem.Code ?? CodeFromType(problem.Type);
        RequestId = problem.RequestId;
        FieldErrors = problem.Errors ?? [];
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

    /// <summary>Request identifier, when present.</summary>
    public string? RequestId { get; }

    /// <summary>Validation messages grouped by field.</summary>
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
                throw new PlatformException(response.StatusCode, problem);
            }
        }

        response.EnsureSuccessStatusCode();
    }

    private static string? CodeFromType(string? type)
    {
        const string prefix = "https://onenexus.cloud/errors/";
        return type?.StartsWith(prefix, StringComparison.Ordinal) == true ? type[prefix.Length..].Replace('-', '_') : null;
    }

    internal sealed class Problem
    {
        public string? Type { get; init; }
        public string? Title { get; init; }
        public string? Detail { get; init; }
        public string? Instance { get; init; }
        public string? Code { get; init; }
        public string? RequestId { get; init; }
        public Dictionary<string, string[]>? Errors { get; init; }
    }
}
