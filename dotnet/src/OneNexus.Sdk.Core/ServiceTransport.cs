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

    internal ServiceTransport(Uri baseUrl, IAccessTokenCredential credentials, SdkClientOptions? options)
    {
        ArgumentNullException.ThrowIfNull(credentials);
        OidcClient.ValidateEndpoint(baseUrl);
        if (baseUrl.Query.Length != 0)
        {
            throw new ArgumentException("The service URL must not include a query.", nameof(baseUrl));
        }

        options ??= new SdkClientOptions();
        ArgumentNullException.ThrowIfNull(options.Context);
        ArgumentOutOfRangeException.ThrowIfNegative(options.MaxRetries);
        ArgumentOutOfRangeException.ThrowIfLessThan(options.MaxRetryDelay, TimeSpan.Zero);
        _pipeline = new HttpClient(new Handler(credentials, options)) { Timeout = options.Timeout };
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
        await operation.ConfigureAwait(false) ?? throw new InvalidDataException("CAS returned an empty response for a typed operation.");

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

    private sealed class Handler : HttpMessageHandler
    {
        private readonly IAccessTokenCredential _credentials;
        private readonly SdkClientOptions _options;

        internal Handler(IAccessTokenCredential credentials, SdkClientOptions options)
        {
            _credentials = credentials;
            _options = options;
        }

        protected override async Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
        {
            Uri uri = request.RequestUri ?? throw new InvalidOperationException("Missing generated request URI.");
            TokenRoute? route = request.GetRequestOption<TokenRoute>();
            AccessToken? fixedToken = null;
            if (route is not null)
            {
                fixedToken = await _credentials.GetTokenAsync(_options.Context, cancellationToken).ConfigureAwait(false);
                uri = new Uri(route.SelectOrigin(fixedToken.Value), uri.PathAndQuery);
            }

            // Kiota serializes once. Each HTTP attempt owns a fresh message with the same body and operation headers.
            var body = request.Content is null ? null : await request.Content.ReadAsByteArrayAsync(cancellationToken).ConfigureAwait(false);
            AccessToken? nextToken = fixedToken;
            for (var attempt = 0; ; attempt++)
            {
                AccessToken token = nextToken ?? await _credentials.GetTokenAsync(_options.Context, cancellationToken).ConfigureAwait(false);
                nextToken = fixedToken;
                using HttpRequestMessage outgoing = CreateAttempt(request, uri, body, token);
                HttpResponseMessage response;
                try
                {
                    response = await (_options.HttpClient ?? SharedHttp).SendAsync(outgoing, cancellationToken).ConfigureAwait(false);
                }
                catch (HttpRequestException ex) when (attempt < _options.MaxRetries && ex.StatusCode is null)
                {
                    await Task.Delay(Backoff(attempt), cancellationToken).ConfigureAwait(false);
                    continue;
                }

                if (response.Headers.Date is DateTimeOffset serverTime)
                {
                    _options.Context.Observe(serverTime);
                }
                if (response.IsSuccessStatusCode)
                {
                    return response;
                }

                TimeSpan? delay = null;
                using (response)
                {
                    if (attempt < _options.MaxRetries)
                    {
                        if (response.StatusCode == HttpStatusCode.Unauthorized && route is null)
                        {
                            AccessToken replacement = await _credentials.GetTokenAsync(_options.Context, cancellationToken).ConfigureAwait(false);
                            if (!string.Equals(replacement.Value, token.Value, StringComparison.Ordinal))
                            {
                                nextToken = replacement;
                                continue;
                            }
                        }
                        else if ((int)response.StatusCode is 408 or 429 or 500 or 502 or 503 or 504)
                        {
                            RetryConditionHeaderValue? after = response.Headers.RetryAfter;
                            delay = after?.Delta ?? (after?.Date - _options.Context.UtcNow) ?? Backoff(attempt);
                        }
                    }
                    if (delay is null || delay > _options.MaxRetryDelay)
                    {
                        await PlatformException.ThrowIfFailedAsync(response, cancellationToken).ConfigureAwait(false);
                    }
                }
                if (delay > TimeSpan.Zero)
                {
                    await Task.Delay(delay.Value, cancellationToken).ConfigureAwait(false);
                }
            }
        }

        private static HttpRequestMessage CreateAttempt(HttpRequestMessage template, Uri uri, byte[]? body, AccessToken token)
        {
            var message = new HttpRequestMessage(template.Method, uri);
            foreach (KeyValuePair<string, IEnumerable<string>> header in template.Headers)
            {
                message.Headers.TryAddWithoutValidation(header.Key, header.Value);
            }
            message.Headers.Authorization = new AuthenticationHeaderValue("Bearer", token.Value);
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
