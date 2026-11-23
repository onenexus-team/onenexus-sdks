using System;
using System.Collections.Generic;
using System.Net;
using System.Net.Http;
using System.Net.Http.Json;
using System.Runtime.CompilerServices;
using System.Security.Authentication;
using System.Text.Json;
using System.Threading.Tasks;

namespace OneNexus.Sdk.Core;

/// <summary>Configuration for grants acquired from an OpenID Connect issuer.</summary>
public sealed class OidcOptions
{
    /// <summary>Sets the CAS issuer exactly as advertised in discovery metadata.</summary>
    public OidcOptions(Uri issuer) => Issuer = OidcClient.ValidateEndpoint(issuer);

    /// <summary>The CAS issuer, which also identifies the audience for private-key assertions.</summary>
    public Uri Issuer { get; }

    /// <summary>Preconfigured token endpoint. Omit to discover it from the issuer.</summary>
    public Uri? TokenEndpoint { get; init; }

    /// <summary>Registered OAuth client identifier.</summary>
    public string? ClientId { get; init; }

    /// <summary>Optional audience requested for the resulting service token.</summary>
    public string? Audience { get; init; }

    /// <summary>Optional space-delimited OAuth scopes.</summary>
    public string? Scope { get; init; }

    /// <summary>Optional caller-owned HTTP client for discovery and token requests.</summary>
    public HttpClient? HttpClient { get; init; }
}

internal sealed class OidcClient
{
    private readonly OidcOptions _options;
    private readonly HttpClient _http;
    private Uri? _tokenEndpoint;

    internal OidcClient(OidcOptions options)
    {
        _options = options ?? throw new ArgumentNullException(nameof(options));
        _http = options.HttpClient ?? ServiceTransport.SharedHttp;
        _tokenEndpoint = options.TokenEndpoint is null ? null : ValidateEndpoint(options.TokenEndpoint);
    }

    internal static Uri ValidateEndpoint(Uri uri, [CallerArgumentExpression(nameof(uri))] string? paramName = null)
    {
        ArgumentNullException.ThrowIfNull(uri, paramName);
        if (!uri.IsAbsoluteUri || (uri.Scheme != Uri.UriSchemeHttps && !(uri.IsLoopback && uri.Scheme == Uri.UriSchemeHttp))
            || uri.UserInfo.Length != 0 || uri.Fragment.Length != 0)
        {
            throw new ArgumentException("Use an absolute HTTPS endpoint or a loopback HTTP endpoint.", paramName);
        }

        return uri;
    }

    internal async Task<TokenGrant> ExchangeAsync(Dictionary<string, string> form, ClientContext context, TokenGrant? prior = null)
    {
        _tokenEndpoint ??= await DiscoverEndpointAsync().ConfigureAwait(false);
        if (_options.ClientId is not null)
        {
            form.Add("client_id", _options.ClientId);
        }

        if (prior is null)
        {
            if (_options.Audience is not null)
            {
                form.Add("audience", _options.Audience);
            }
            if (_options.Scope is not null)
            {
                form.Add("scope", _options.Scope);
            }
        }

        using var body = new FormUrlEncodedContent(form);
        using HttpResponseMessage response = await _http.PostAsync(_tokenEndpoint, body).ConfigureAwait(false);
        if (response.Headers.Date is DateTimeOffset serverTime)
        {
            context.Observe(serverTime);
        }
        if (response.StatusCode is HttpStatusCode.Unauthorized or HttpStatusCode.Forbidden)
        {
            throw new AuthenticationException("CAS rejected the token grant.");
        }
        if (response.StatusCode == HttpStatusCode.BadRequest)
        {
            using JsonDocument? error = await TryReadErrorAsync(response).ConfigureAwait(false);
            if (error?.RootElement.ValueKind == JsonValueKind.Object && error.RootElement.TryGetProperty("error", out JsonElement code)
                && code.ValueKind == JsonValueKind.String && code.GetString() is "invalid_grant" or "invalid_client")
            {
                throw new AuthenticationException("CAS rejected the token grant.");
            }
        }

        response.EnsureSuccessStatusCode();
        JsonElement json = await response.Content.ReadFromJsonAsync(SdkJsonContext.Default.JsonElement).ConfigureAwait(false);
        var value = json.GetProperty("access_token").GetString();
        if (string.IsNullOrWhiteSpace(value) || (json.TryGetProperty("token_type", out JsonElement type)
            && !string.Equals(type.GetString(), "Bearer", StringComparison.OrdinalIgnoreCase)))
        {
            throw new JsonException("CAS did not return a bearer access token.");
        }

        var seconds = json.TryGetProperty("expires_in", out JsonElement expiry) ? expiry.GetInt64() : 3600;
        DateTimeOffset now = context.UtcNow;
        if (seconds <= 0 || seconds > (DateTimeOffset.MaxValue - now).TotalSeconds)
        {
            throw new JsonException("Invalid token lifetime.");
        }

        return new TokenGrant(new AccessToken(value, now.AddSeconds(seconds)) { Lifetime = TimeSpan.FromSeconds(seconds) })
        {
            RefreshToken = json.TryGetProperty("refresh_token", out JsonElement refresh) ? refresh.GetString() : prior?.RefreshToken,
            IdToken = json.TryGetProperty("id_token", out JsonElement id) ? id.GetString() : prior?.IdToken,
            Scopes = json.TryGetProperty("scope", out JsonElement scope)
                ? scope.GetString()?.Split(' ', StringSplitOptions.RemoveEmptyEntries) ?? []
                : prior?.Scopes ?? [],
        };
    }

    private async Task<Uri> DiscoverEndpointAsync()
    {
        var url = new Uri(_options.Issuer.AbsoluteUri.TrimEnd('/') + "/.well-known/openid-configuration");
        JsonElement metadata = await _http.GetFromJsonAsync(url, SdkJsonContext.Default.JsonElement).ConfigureAwait(false);
        if (metadata.GetProperty("issuer").GetString() != _options.Issuer.OriginalString)
        {
            throw new AuthenticationException("The discovery issuer does not match the configured issuer.");
        }

        return ValidateEndpoint(new Uri(metadata.GetProperty("token_endpoint").GetString() ?? throw new JsonException("Missing token endpoint.")));
    }

    private static async Task<JsonDocument?> TryReadErrorAsync(HttpResponseMessage response)
    {
        try
        {
            return await response.Content.ReadFromJsonAsync(SdkJsonContext.Default.JsonDocument).ConfigureAwait(false);
        }
        catch (JsonException)
        {
            return null;
        }
    }
}
