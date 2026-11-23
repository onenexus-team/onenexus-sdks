using System;
using System.Collections.Generic;
using System.Threading.Tasks;
using Microsoft.IdentityModel.JsonWebTokens;
using Microsoft.IdentityModel.Tokens;

namespace OneNexus.Sdk.Core;

/// <summary>Exchanges a signed private-key client assertion for a CAS access token.</summary>
public sealed class PrivateKeyJwtCredentials : CachedCredentials
{
    private readonly OidcOptions _options;
    private readonly OidcClient _oidc;
    private readonly SigningCredentials _signing;

    /// <summary>Uses a registered key with a key ID and the RS256, PS256, or ES256 algorithm.</summary>
    public PrivateKeyJwtCredentials(OidcOptions options, SigningCredentials signing)
    {
        ArgumentNullException.ThrowIfNull(options);
        ArgumentException.ThrowIfNullOrWhiteSpace(options.ClientId);
        ArgumentNullException.ThrowIfNull(signing);
        ArgumentException.ThrowIfNullOrWhiteSpace(signing.Key.KeyId);
        if (signing.Algorithm is not ("RS256" or "PS256" or "ES256"))
        {
            throw new ArgumentException("CAS requires an RS256, PS256 or ES256 signing key.", nameof(signing));
        }

        _options = options;
        _oidc = new OidcClient(options);
        _signing = signing;
    }

    private protected override Task<TokenGrant> RefreshAsync(ClientContext context)
    {
        DateTime now = context.UtcNow.UtcDateTime;
        var descriptor = new SecurityTokenDescriptor
        {
            Issuer = _options.ClientId,
            Audience = _options.Issuer.OriginalString,
            IssuedAt = now,
            NotBefore = now,
            Expires = now.AddMinutes(1),
            TokenType = "client-authentication+jwt",
            SigningCredentials = _signing,
            Claims = new Dictionary<string, object>
            {
                [JwtRegisteredClaimNames.Sub] = _options.ClientId!,
                [JwtRegisteredClaimNames.Jti] = Guid.NewGuid().ToString("N"),
            },
        };
        return _oidc.ExchangeAsync(new Dictionary<string, string>
        {
            ["grant_type"] = "client_credentials",
            ["client_assertion_type"] = "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
            ["client_assertion"] = new JsonWebTokenHandler().CreateToken(descriptor),
        }, context);
    }
}
