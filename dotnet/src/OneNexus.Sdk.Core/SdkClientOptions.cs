using System;
using System.Net;
using System.Net.Http;

namespace OneNexus.Sdk.Core;

/// <summary>Transport options shared by the customer and support clients.</summary>
public sealed class SdkClientOptions
{
    /// <summary>Optional caller-owned HTTP client. Configure it without a second retry policy.</summary>
    public HttpClient? HttpClient { get; init; }

    /// <summary>Creates a caller-owned transport handler with the SDK's HTTP defaults.</summary>
    /// <remarks>Use it as the inner handler for custom middleware. Reuse the resulting HTTP client across requests.</remarks>
    public static SocketsHttpHandler CreateDefaultHttpHandler() => new SocketsHttpHandler
    {
        AllowAutoRedirect = false,
        AutomaticDecompression = DecompressionMethods.All,
        UseCookies = false,
        PooledConnectionLifetime = TimeSpan.FromMinutes(5),
    };

    /// <summary>The credential clock shared across requests made by this client.</summary>
    public ClientContext Context { get; init; } = new ClientContext();

    /// <summary>Maximum retries after the initial attempt. Zero disables retries.</summary>
    public int MaxRetries { get; init; } = 2;

    /// <summary>Maximum retry delay. A longer server Retry-After returns the original error.</summary>
    public TimeSpan MaxRetryDelay { get; init; } = TimeSpan.FromSeconds(5);

    /// <summary>Total timeout for a logical service request including its retries.</summary>
    public TimeSpan Timeout { get; init; } = TimeSpan.FromSeconds(30);
}
