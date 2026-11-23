using System;
using System.Buffers.Text;
using System.Linq;
using System.Text.Json;

namespace OneNexus.Sdk.Cas;

/// <summary>Validates the issuer used to route an AssumeS3Role request.</summary>
internal static class CasRouting
{
    /// <summary>Selects the global origin or a single regional auth host on the same scheme, domain and port.</summary>
    internal static Uri ResolveAssumeS3RoleBaseUrl(Uri globalBaseUrl, string accessToken)
    {
        ArgumentNullException.ThrowIfNull(globalBaseUrl);
        ArgumentException.ThrowIfNullOrWhiteSpace(accessToken);
        if (!IsOrigin(globalBaseUrl) || !globalBaseUrl.IdnHost.StartsWith("auth.", StringComparison.Ordinal)
            || globalBaseUrl.IdnHost.Length <= 5)
        {
            throw new ArgumentException("Configure the global auth.<domain> origin.", nameof(globalBaseUrl));
        }

        var parts = accessToken.Split('.');
        if (parts.Length != 3)
        {
            return globalBaseUrl;
        }

        JsonDocument claims;
        try
        {
            claims = JsonDocument.Parse(Base64Url.DecodeFromChars(parts[1]));
        }
        catch (Exception ex) when (ex is FormatException or JsonException or ArgumentException)
        {
            return globalBaseUrl;
        }

        using (claims)
        {
            if (claims.RootElement.ValueKind != JsonValueKind.Object)
            {
                return globalBaseUrl;
            }
            if (!claims.RootElement.TryGetProperty("iss", out JsonElement iss) || iss.ValueKind != JsonValueKind.String
                || !Uri.TryCreate(iss.GetString(), UriKind.Absolute, out Uri? issuer) || !IsOrigin(issuer))
            {
                throw new ArgumentException("The CAS token has an invalid issuer.", nameof(accessToken));
            }

            if (issuer == globalBaseUrl)
            {
                return globalBaseUrl;
            }

            var host = issuer.IdnHost;
            var suffix = globalBaseUrl.IdnHost[4..];
            if (issuer.Scheme == globalBaseUrl.Scheme && issuer.Port == globalBaseUrl.Port && host.StartsWith("auth.", StringComparison.Ordinal)
                && host.Length > 5 + suffix.Length && host.EndsWith(suffix, StringComparison.Ordinal))
            {
                var region = host[5..^suffix.Length];
                if (region[0] != '-' && region[^1] != '-' && region.All(c => char.IsAsciiLetterOrDigit(c) || c == '-'))
                {
                    return issuer;
                }
            }
            throw new ArgumentException("The CAS token issuer is outside the configured regional origins.", nameof(accessToken));
        }
    }

    private static bool IsOrigin(Uri uri) => uri.IsAbsoluteUri && uri.Scheme is "http" or "https"
        && uri.AbsolutePath == "/" && uri.UserInfo.Length == 0 && uri.Query.Length == 0 && uri.Fragment.Length == 0;
}
