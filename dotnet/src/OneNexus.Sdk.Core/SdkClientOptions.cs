using System;
using System.Net.Http;

namespace OneNexus.Sdk.Core;

/// <summary>Transport options shared by the customer and support clients.</summary>
public sealed class SdkClientOptions
{
    /// <summary>Optional caller-owned HTTP client. Configure it without a second retry policy.</summary>
    public HttpClient? HttpClient { get; init; }

    /// <summary>The credential clock shared across requests made by this client.</summary>
    public ClientContext Context { get; init; } = new ClientContext();

    /// <summary>Maximum retries after the initial attempt. Zero disables retries.</summary>
    public int MaxRetries { get; init; } = 2;

    /// <summary>Upper bound for retry delays, including Retry-After.</summary>
    public TimeSpan MaxRetryDelay { get; init; } = TimeSpan.FromSeconds(5);

    /// <summary>Total timeout for a logical service request including its retries.</summary>
    public TimeSpan Timeout { get; init; } = TimeSpan.FromSeconds(30);
}
