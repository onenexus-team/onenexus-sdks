using System;
using System.Linq;
using System.Net;
using System.Net.Http;
using System.Runtime.CompilerServices;
using System.Security.Cryptography;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.IdentityModel.Tokens;
using OneNexus.Sdk.Cas;
using OneNexus.Sdk.Cas.Models;
using OneNexus.Sdk.Cas.Support;
using OneNexus.Sdk.Core;
using OneNexus.Sdk.MLOps;
using OneNexus.Sdk.MLOps.Models;
using OneNexus.Sdk.Tests;

namespace OneNexus.Sdk.NativeAotProbe;

internal static class Program
{
    private static readonly Uri Issuer = new Uri("https://auth.example.test");

    private static async Task Main()
    {
        if (RuntimeFeature.IsDynamicCodeSupported || JsonSerializer.IsReflectionEnabledByDefault)
        {
            throw new InvalidOperationException("Run the Native AOT executable with reflection-based JSON disabled.");
        }

        using var http = new HttpClient(new TestHandler(RespondAsync));
        var oidc = new OidcOptions(Issuer) { ClientId = "native-cli", HttpClient = http };
        var expired = new TokenGrant(new AccessToken("expired", DateTimeOffset.UnixEpoch)) { RefreshToken = "before" };
        var credentials = new TokenGrantCredentials(expired, oidc);
        var options = new SdkClientOptions { HttpClient = http, MaxRetries = 0 };
        using var cas = new CasClient(Issuer, credentials, options);

        GetPolicyResponse result = await cas.GetPolicyAsync(new GetPolicyRequest { Name = "example", Kind = AuthorizationPolicyKind.TenantManaged });
        if (result.Policy?.Kind != AuthorizationPolicyKind.TenantManaged || result.Policy.Document is null || credentials.Snapshot.RefreshToken != "after")
        {
            throw new InvalidOperationException("Failed to decode the policy or refresh the grant.");
        }
        await cas.PublishPolicyAsync(new PublishPolicyRequest { Name = "example", Document = result.Policy.Document });

        using var rsa = RSA.Create(2048);
        var signingKey = new RsaSecurityKey(rsa) { KeyId = "probe" };
        var service = new PrivateKeyJwtCredentials(oidc, new SigningCredentials(signingKey, SecurityAlgorithms.RsaSha256));
        using var support = new CasSupportClient(Issuer, service, options);
        if ((await support.ListTenantsAsync()).Items?.Single().DisplayName != "Example")
        {
            throw new InvalidOperationException("Failed to read the support response.");
        }

        using var mlops = new MLOpsClient(new Uri("https://mlops.example.test"), credentials, options);
        ListResponse_DatasetSummaryResponse_ datasets = await mlops.ListDatasetsAsync(new RpcListDatasetsRequest { Name = "training" });
        if (datasets.TotalPages != 1 || datasets.Items?.Single().Name != "training")
        {
            throw new InvalidOperationException("Failed to read the MLOps dataset page.");
        }

        try
        {
            await cas.ListUsersAsync();
            throw new InvalidOperationException("Expected CAS validation error.");
        }
        catch (PlatformException error) when (error.StatusCode == HttpStatusCode.BadRequest
            && error.Code == "invalid_argument" && error.FieldErrors["name"].Single() == "required")
        {
            Console.WriteLine("Native AOT passed for CAS, CAS Support, MLOps, credentials and Problem Details.");
        }
    }

    private static async Task<HttpResponseMessage> RespondAsync(HttpRequestMessage request, CancellationToken cancellationToken)
    {
        switch (request.RequestUri?.AbsolutePath)
        {
            case "/.well-known/openid-configuration":
                return TestHandler.Json("""{"issuer":"https://auth.example.test","token_endpoint":"https://auth.example.test/connect/token"}""");
            case "/connect/token":
                var form = await request.Content!.ReadAsStringAsync(cancellationToken);
                if (form.Contains("refresh_token=before", StringComparison.Ordinal))
                {
                    return TestHandler.Json("""{"access_token":"user","expires_in":3600,"refresh_token":"after"}""");
                }
                if (form.Contains("client_assertion=", StringComparison.Ordinal))
                {
                    return TestHandler.Json("""{"access_token":"service","expires_in":3600}""");
                }
                break;
            case "/api/GetPolicy" when request.Headers.Authorization?.Parameter == "user":
                using (var body = JsonDocument.Parse(await request.Content!.ReadAsStringAsync(cancellationToken)))
                {
                    if (body.RootElement.GetProperty("kind").GetString() == "TenantManaged")
                    {
                        return TestHandler.Json("""{"policy":{"kind":"TenantManaged","document":{"rules":[{"enabled":true}]}}}""");
                    }
                }
                break;
            case "/api/PublishPolicy":
                using (var body = JsonDocument.Parse(await request.Content!.ReadAsStringAsync(cancellationToken)))
                {
                    if (body.RootElement.GetProperty("document").GetProperty("rules")[0].GetProperty("enabled").GetBoolean())
                    {
                        return TestHandler.Json("{}");
                    }
                }
                break;
            case "/support-api/ListTenants" when request.Headers.Authorization?.Parameter == "service":
                return TestHandler.Json("""{"items":[{"displayName":"Example"}]}""");
            case "/api/v1/DataHub/ListDatasets" when request.Headers.Authorization?.Parameter == "user":
                using (var body = JsonDocument.Parse(await request.Content!.ReadAsStringAsync(cancellationToken)))
                {
                    if (body.RootElement.GetProperty("name").GetString() == "training")
                    {
                        return TestHandler.Json("""{"items":[{"name":"training"}],"total_pages":1}""");
                    }
                }
                break;
            case "/api/ListUsers":
                return TestHandler.Json("""{"type":"https://onenexus.cloud/errors/invalid-argument","errors":{"name":["required"]}}""",
                    HttpStatusCode.BadRequest, "application/problem+json");
        }
        throw new InvalidOperationException("Unexpected probe request.");
    }
}
