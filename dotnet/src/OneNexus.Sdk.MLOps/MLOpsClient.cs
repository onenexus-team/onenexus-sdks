using System;
using System.Linq;
using Microsoft.Kiota.Abstractions;
using OneNexus.Sdk.Core;

namespace OneNexus.Sdk.MLOps;

/// <summary>Typed client for the OneNexus MLOps service's public HTTP API.</summary>
public sealed partial class MLOpsClient : IDisposable
{
    private readonly ServiceTransport _transport;
    private readonly MLOpsGeneratedClient _api;

    /// <summary>Connects to the MLOps service root. Supply CAS credentials for control-plane operations.</summary>
    public MLOpsClient(Uri baseUrl, IAccessTokenCredential? credentials = null, SdkClientOptions? options = null)
    {
        _transport = new ServiceTransport(baseUrl, credentials, options);
        _api = new MLOpsGeneratedClient(_transport.Adapter);
    }

    private static void AddIdempotencyKey(RequestConfiguration<DefaultQueryParameters> config, string? idempotencyKey)
    {
        var key = idempotencyKey ?? Guid.NewGuid().ToString("D");
        if (key.Length is < 1 or > 255 || key.Any(c => c is < '!' or > '~'))
        {
            throw new ArgumentException("MLOps expects 1 to 255 visible ASCII characters.", nameof(idempotencyKey));
        }
        config.Headers.Add("Idempotency-Key", key);
    }

    private static void UseAnonymous(RequestConfiguration<DefaultQueryParameters> config) =>
        config.Options.Add(new ServiceTransport.RequestPolicy { UseClientCredentials = false });

    private static void DisableRetries(RequestConfiguration<DefaultQueryParameters> config) =>
        config.Options.Add(new ServiceTransport.RequestPolicy { AllowRetries = false });

    private static void UsePlatformKey(RequestConfiguration<DefaultQueryParameters> config, string platformApiKey, bool retry)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(platformApiKey);
        if (platformApiKey.Any(c => c is < '!' or > '~'))
        {
            throw new ArgumentException("A bearer API key must contain only visible ASCII characters.", nameof(platformApiKey));
        }
        config.Headers.Add("Authorization", "Bearer " + platformApiKey);
        config.Options.Add(new ServiceTransport.RequestPolicy { UseClientCredentials = false, AllowRetries = retry });
    }

    /// <summary>Releases this client's transport. The caller owns an injected HTTP client.</summary>
    public void Dispose() => _transport.Dispose();
}
