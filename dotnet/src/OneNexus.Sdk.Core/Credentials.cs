using System;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;

namespace OneNexus.Sdk.Core;

/// <summary>A bearer token and its absolute expiry time.</summary>
public sealed class AccessToken
{
    /// <summary>Creates a token obtained from CAS.</summary>
    public AccessToken(string value, DateTimeOffset expiresAt)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(value);
        Value = value;
        ExpiresAt = expiresAt;
    }

    /// <summary>The bearer token sent to the service.</summary>
    public string Value { get; }

    /// <summary>Absolute token expiry.</summary>
    public DateTimeOffset ExpiresAt { get; }

    internal TimeSpan? Lifetime { get; init; }
}

/// <summary>A grant returned by CAS or an external login flow.</summary>
public sealed class TokenGrant
{
    /// <summary>Creates a grant with an access token and optional login metadata.</summary>
    public TokenGrant(AccessToken accessToken) => AccessToken = accessToken ?? throw new ArgumentNullException(nameof(accessToken));

    /// <summary>The current access token.</summary>
    public AccessToken AccessToken { get; }

    /// <summary>Refresh token, including the most recent rotation.</summary>
    public string? RefreshToken { get; init; }

    /// <summary>Identity token returned by the login flow.</summary>
    public string? IdToken { get; init; }

    /// <summary>Scopes granted by CAS.</summary>
    public IReadOnlyList<string> Scopes { get; init; } = [];
}

/// <summary>Supplies bearer tokens for OneNexus service requests.</summary>
public interface IAccessTokenCredential
{
    /// <summary>Resolves an access token using the service clock and refresh leeway.</summary>
    ValueTask<AccessToken> GetTokenAsync(ClientContext context, CancellationToken cancellationToken = default);
}

/// <summary>Provides a server-adjusted clock for credential expiry and refresh.</summary>
public sealed class ClientContext
{
    private readonly TimeProvider _clock;
    private long _offsetTicks;

    /// <summary>Creates a context using a 30-second refresh window by default.</summary>
    public ClientContext(TimeProvider? clock = null, TimeSpan? refreshLeeway = null)
    {
        _clock = clock ?? TimeProvider.System;
        RefreshLeeway = refreshLeeway ?? TimeSpan.FromSeconds(30);
        ArgumentOutOfRangeException.ThrowIfLessThan(RefreshLeeway, TimeSpan.Zero);
    }

    /// <summary>The time before expiry at which credentials refresh.</summary>
    public TimeSpan RefreshLeeway { get; }

    /// <summary>Current time corrected by the most recent service Date header.</summary>
    public DateTimeOffset UtcNow => _clock.GetUtcNow().AddTicks(Interlocked.Read(ref _offsetTicks));

    internal void Observe(DateTimeOffset serverTime) => Interlocked.Exchange(ref _offsetTicks, (serverTime - _clock.GetUtcNow()).Ticks);
}

/// <summary>The stored grant has expired or needs refreshing and has no refresh configuration.</summary>
public sealed class StaleCredentialsException : InvalidOperationException
{
    internal StaleCredentialsException() : base("The access token is stale and no refresh grant is configured.") { }
}

/// <summary>Shares one grant acquisition across concurrent callers of a credential.</summary>
public abstract class CachedCredentials : IAccessTokenCredential
{
    private readonly Lock _refreshGate = new Lock();
    private TokenGrant? _grant;
    private Task<AccessToken>? _refresh;

    private protected CachedCredentials(TokenGrant? grant = null) => _grant = grant;

    private protected TokenGrant? CurrentGrant => Volatile.Read(ref _grant);

    /// <inheritdoc/>
    public ValueTask<AccessToken> GetTokenAsync(ClientContext context, CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(context);
        cancellationToken.ThrowIfCancellationRequested();
        if (GetFreshToken(context) is AccessToken cached)
        {
            return ValueTask.FromResult(cached);
        }

        Task<AccessToken> refresh;
        lock (_refreshGate)
        {
            if (_refresh is null || _refresh.IsCompleted)
            {
                // Another caller may have finished refreshing while we waited for the gate.
                if (GetFreshToken(context) is AccessToken refreshed)
                {
                    return ValueTask.FromResult(refreshed);
                }

                _refresh = RefreshAndStoreAsync(context);
            }
            refresh = _refresh;
        }

        // Cancel only this wait. Other callers can still use the grant being acquired.
        return new ValueTask<AccessToken>(refresh.WaitAsync(cancellationToken));
    }

    private AccessToken? GetFreshToken(ClientContext context)
    {
        AccessToken? token = CurrentGrant?.AccessToken;
        if (token is null)
        {
            return null;
        }

        TimeSpan leeway = context.RefreshLeeway;
        if (token.Lifetime is TimeSpan lifetime && lifetime / 2 < leeway)
        {
            leeway = lifetime / 2;
        }
        return token.ExpiresAt - context.UtcNow > leeway ? token : null;
    }

    private async Task<AccessToken> RefreshAndStoreAsync(ClientContext context)
    {
        TokenGrant grant = await RefreshAsync(context).ConfigureAwait(false);
        Volatile.Write(ref _grant, grant);
        return grant.AccessToken;
    }

    private protected abstract Task<TokenGrant> RefreshAsync(ClientContext context);
}
