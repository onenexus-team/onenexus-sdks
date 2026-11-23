using System;
using System.Collections.Generic;
using System.Threading.Tasks;

namespace OneNexus.Sdk.Core;

/// <summary>Uses an existing access token and optionally refreshes the grant when it nears expiry.</summary>
public sealed class TokenGrantCredentials : CachedCredentials
{
    private readonly OidcClient? _oidc;

    /// <summary>Uses a bearer token obtained by the application.</summary>
    public TokenGrantCredentials(AccessToken accessToken) : this(new TokenGrant(accessToken)) { }

    /// <summary>Enables refresh when the grant has a refresh token and options identify an OAuth client.</summary>
    public TokenGrantCredentials(TokenGrant grant, OidcOptions? options = null)
        : base(grant ?? throw new ArgumentNullException(nameof(grant)))
    {
        if (options is not null)
        {
            ArgumentException.ThrowIfNullOrWhiteSpace(options.ClientId);
            _oidc = new OidcClient(options);
        }
    }

    /// <summary>The latest grant, including any rotated refresh token.</summary>
    public TokenGrant Snapshot => CurrentGrant ?? throw new InvalidOperationException("Missing initial grant.");

    private protected override Task<TokenGrant> RefreshAsync(ClientContext context)
    {
        TokenGrant grant = Snapshot;
        if (_oidc is null || string.IsNullOrWhiteSpace(grant.RefreshToken))
        {
            throw new StaleCredentialsException();
        }

        return _oidc.ExchangeAsync(new Dictionary<string, string>
        {
            ["grant_type"] = "refresh_token",
            ["refresh_token"] = grant.RefreshToken,
        }, context, grant);
    }
}
