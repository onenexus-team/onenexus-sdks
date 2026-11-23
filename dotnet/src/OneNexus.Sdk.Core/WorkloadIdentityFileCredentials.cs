using System;
using System.Collections.Generic;
using System.IO;
using System.Threading.Tasks;

namespace OneNexus.Sdk.Core;

/// <summary>Exchanges a runtime-mounted identity token, reading the file again on every refresh.</summary>
public sealed class WorkloadIdentityFileCredentials : CachedCredentials
{
    /// <summary>Default location of the projected OneNexus workload token.</summary>
    public const string DefaultTokenPath = "/var/run/secrets/onenexus/token";

    private readonly OidcClient _oidc;
    private readonly string _tokenPath;

    /// <summary>Uses CAS discovery or the configured token endpoint to acquire workload credentials.</summary>
    public WorkloadIdentityFileCredentials(OidcOptions options, string tokenPath = DefaultTokenPath)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(tokenPath);
        _oidc = new OidcClient(options);
        _tokenPath = tokenPath;
    }

    private protected override async Task<TokenGrant> RefreshAsync(ClientContext context)
    {
        var subject = (await File.ReadAllTextAsync(_tokenPath).ConfigureAwait(false)).Trim();
        if (subject.Length == 0)
        {
            throw new InvalidDataException("The workload identity token file is empty.");
        }

        return await _oidc.ExchangeAsync(new Dictionary<string, string>
        {
            ["grant_type"] = "urn:onenexus:params:oauth:grant-type:workload-identity",
            ["subject_token_type"] = "urn:ietf:params:oauth:token-type:jwt",
            ["subject_token"] = subject,
        }, context).ConfigureAwait(false);
    }
}
