using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Net;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Kiota.Abstractions;
using Microsoft.Kiota.Abstractions.Authentication;
using Microsoft.Kiota.Http.HttpClientLibrary;
using Microsoft.Kiota.Http.HttpClientLibrary.Extensions;

namespace OneNexus.Sdk.Core;

internal sealed class ServiceTransport : IDisposable
{
    internal static readonly HttpClient SharedHttp = new HttpClient(new SocketsHttpHandler
    {
        AllowAutoRedirect = false,
        AutomaticDecompression = DecompressionMethods.All,
        UseCookies = false,
        PooledConnectionLifetime = TimeSpan.FromMinutes(5),
    });

    private readonly HttpClient _pipeline;

    internal ServiceTransport(Uri baseUrl, IAccessTokenCredential? credentials, SdkClientOptions? options)
    {
        OidcClient.ValidateEndpoint(baseUrl);
        if (baseUrl.Query.Length != 0)
        {
            throw new ArgumentException("The service URL must not include a query.", nameof(baseUrl));
        }

        options ??= new SdkClientOptions();
        ArgumentNullException.ThrowIfNull(options.Context);
        ArgumentOutOfRangeException.ThrowIfNegative(options.MaxRetries);
        ArgumentOutOfRangeException.ThrowIfLessThan(options.MaxRetryDelay, TimeSpan.Zero);
        var handler = new Handler(credentials, options);
        _pipeline = new HttpClient(new ProblemHandler { InnerHandler = handler }) { Timeout = options.Timeout };
        Adapter = new HttpClientRequestAdapter(new AnonymousAuthenticationProvider(), httpClient: _pipeline)
        {
            BaseUrl = baseUrl.AbsoluteUri.TrimEnd('/'),
        };
    }

    internal HttpClientRequestAdapter Adapter { get; }

    internal static Action<RequestConfiguration<DefaultQueryParameters>> WithIdempotencyKey(string? idempotencyKey)
    {
        var key = idempotencyKey ?? Guid.NewGuid().ToString("D");
        if (key.Length is < 16 or > 128 || !key.All(c => char.IsAsciiLetterOrDigit(c) || c is '_' or '-' or '.'))
        {
            throw new ArgumentException("Expected 16–128 ASCII letters, digits, underscores, dots or hyphens.", nameof(idempotencyKey));
        }
        return configuration => configuration.Headers.Add("X-Nx1-Idempotency-Key", key);
    }

    internal static async Task<T> RequiredAsync<T>(Task<T?> operation) where T : class =>
        await operation.ConfigureAwait(false) ?? throw new InvalidDataException("The service returned an empty response for a typed operation.");

    public void Dispose()
    {
        Adapter.Dispose();
        _pipeline.Dispose();
    }

    internal sealed class TokenRoute : IRequestOption
    {
        internal TokenRoute(Func<string, Uri> selectOrigin) => SelectOrigin = selectOrigin;

        internal Func<string, Uri> SelectOrigin { get; }
    }

    internal sealed class RequestPolicy : IRequestOption
    {
        internal bool UseClientCredentials { get; init; } = true;
        internal bool AllowRetries { get; init; } = true;
    }

    private sealed class ProblemHandler : DelegatingHandler
    {
        protected override async Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
        {
            HttpResponseMessage response = await base.SendAsync(request, cancellationToken).ConfigureAwait(false);
            try
            {
                await PlatformException.ThrowIfFailedAsync(response, cancellationToken).ConfigureAwait(false);
                return response;
            }
            catch
            {
                response.Dispose();
                throw;
            }
        }
    }

    private sealed class Handler : HttpMessageHandler
    {
        private readonly IAccessTokenCredential? _credentials;
        private readonly SdkClientOptions _options;

        internal Handler(IAccessTokenCredential? credentials, SdkClientOptions options)
        {
            _credentials = credentials;
            _options = options;
        }

        protected override async Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
        {
            Uri uri = request.RequestUri ?? throw new InvalidOperationException("Missing generated request URI.");
            TokenRoute? route = request.GetRequestOption<TokenRoute>();
            RequestPolicy? policy = request.GetRequestOption<RequestPolicy>();
            var useClientCredentials = policy?.UseClientCredentials ?? true;
            var maxRetries = policy?.AllowRetries == false ? 0 : _options.MaxRetries;
            AccessToken? fixedToken = null;
            if (route is not null)
            {
                fixedToken = await GetTokenAsync(cancellationToken).ConfigureAwait(false);
                uri = new Uri(route.SelectOrigin(fixedToken.Value), uri.PathAndQuery);
            }

            // Kiota serializes once. Each HTTP attempt owns a fresh message with the same body and operation headers.
            var body = request.Content is null ? null : await request.Content.ReadAsByteArrayAsync(cancellationToken).ConfigureAwait(false);
            AccessToken? nextToken = fixedToken;
            for (var attempt = 0; ; attempt++)
            {
                AccessToken? token = nextToken;
                if (token is null && useClientCredentials)
                {
                    token = await GetTokenAsync(cancellationToken).ConfigureAwait(false);
                }
                nextToken = fixedToken;
                using HttpRequestMessage outgoing = CreateAttempt(request, uri, body, token);
                HttpResponseMessage response;
                try
                {
                    response = await (_options.HttpClient ?? SharedHttp).SendAsync(outgoing, cancellationToken).ConfigureAwait(false);
                }
                catch (HttpRequestException ex) when (attempt < maxRetries && ex.StatusCode is null)
                {
                    await Task.Delay(Backoff(attempt), cancellationToken).ConfigureAwait(false);
                    continue;
                }

                if (response.Headers.Date is DateTimeOffset serverTime)
                {
                    _options.Context.Observe(serverTime);
                }
                if (response.IsSuccessStatusCode || attempt >= maxRetries)
                {
                    return response;
                }

                if (response.StatusCode == HttpStatusCode.Unauthorized && token is not null && route is null)
                {
                    AccessToken replacement;
                    try
                    {
                        replacement = await GetTokenAsync(cancellationToken).ConfigureAwait(false);
                    }
                    catch
                    {
                        response.Dispose();
                        throw;
                    }
                    if (string.Equals(replacement.Value, token.Value, StringComparison.Ordinal))
                    {
                        return response;
                    }
                    response.Dispose();
                    nextToken = replacement;
                    continue;
                }
                if ((int)response.StatusCode is not (408 or 429 or 500 or 502 or 503 or 504))
                {
                    return response;
                }

                RetryConditionHeaderValue? after = response.Headers.RetryAfter;
                TimeSpan delay = after?.Delta ?? (after?.Date - _options.Context.UtcNow) ?? Backoff(attempt);
                if (delay > _options.MaxRetryDelay)
                {
                    return response;
                }
                response.Dispose();
                if (delay > TimeSpan.Zero)
                {
                    await Task.Delay(delay, cancellationToken).ConfigureAwait(false);
                }
            }
        }

        private ValueTask<AccessToken> GetTokenAsync(CancellationToken cancellationToken) =>
            (_credentials ?? throw new InvalidOperationException("This operation requires CAS credentials. Supply them when constructing the client."))
                .GetTokenAsync(_options.Context, cancellationToken);

        private static HttpRequestMessage CreateAttempt(HttpRequestMessage template, Uri uri, byte[]? body, AccessToken? token)
        {
            var message = new HttpRequestMessage(template.Method, uri);
            foreach (KeyValuePair<string, IEnumerable<string>> header in template.Headers)
            {
                message.Headers.TryAddWithoutValidation(header.Key, header.Value);
            }
            if (token is not null)
            {
                message.Headers.Authorization = new AuthenticationHeaderValue("Bearer", token.Value);
            }
            if (body is not null && template.Content is not null)
            {
                message.Content = new ByteArrayContent(body);
                foreach (KeyValuePair<string, IEnumerable<string>> header in template.Content.Headers)
                {
                    message.Content.Headers.TryAddWithoutValidation(header.Key, header.Value);
                }
            }
            return message;
        }

        private TimeSpan Backoff(int attempt)
        {
            var milliseconds = Random.Shared.NextDouble() * 300 * Math.Pow(2, Math.Min(attempt, 30));
            return TimeSpan.FromMilliseconds(Math.Min(milliseconds, _options.MaxRetryDelay.TotalMilliseconds));
        }
    }
}
