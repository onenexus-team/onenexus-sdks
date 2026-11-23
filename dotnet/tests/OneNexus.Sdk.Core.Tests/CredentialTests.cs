using System;
using System.Collections.Generic;
using System.Collections.Specialized;
using System.IO;
using System.Net;
using System.Net.Http;
using System.Security.Authentication;
using System.Security.Cryptography;
using System.Threading;
using System.Threading.Tasks;
using System.Web;
using Microsoft.IdentityModel.JsonWebTokens;
using Microsoft.IdentityModel.Tokens;
using Microsoft.VisualStudio.TestTools.UnitTesting;
using OneNexus.Sdk.Tests;

namespace OneNexus.Sdk.Core.Tests;

[TestClass]
public sealed class CredentialTests
{
    private static readonly string[] ExpectedRefreshTokens = ["initial", "rotated"];
    private static readonly string[] ExpectedSubjects = ["first", "second"];
    private static readonly Uri Issuer = new Uri("https://issuer.example.test");
    private static readonly Uri Endpoint = new Uri(Issuer, "connect/token");

    [TestMethod]
    public async Task FreshAndStaleExternalTokens()
    {
        var context = new ClientContext();
        var token = new AccessToken("external", context.UtcNow.AddMinutes(5));
        using var credential = new TokenGrantCredentials(token);
        ValueTask<AccessToken> hit = credential.GetTokenAsync(context);
        Assert.IsTrue(hit.IsCompletedSuccessfully);
        Assert.AreSame(token, await hit);
        using var stale = new TokenGrantCredentials(new AccessToken("expired", context.UtcNow));
        await Assert.ThrowsExactlyAsync<StaleCredentialsException>(() => stale.GetTokenAsync(context).AsTask());
    }

    [TestMethod]
    public async Task ConcurrentRefreshSharesDiscoveryAndRotatesTheGrant()
    {
        var started = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
        var complete = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
        var discoveryCount = 0;
        var grants = new List<string?>();
        using var http = new HttpClient(new TestHandler(async (request, ct) =>
        {
            if (request.Method == HttpMethod.Get)
            {
                discoveryCount++;
                Assert.AreEqual("/.well-known/openid-configuration", request.RequestUri?.AbsolutePath);
                return TestHandler.Json("""{"issuer":"https://issuer.example.test","token_endpoint":"https://issuer.example.test/connect/token"}""");
            }
            Assert.AreEqual(Endpoint, request.RequestUri);
            NameValueCollection form = HttpUtility.ParseQueryString(await request.Content!.ReadAsStringAsync(ct));
            Assert.AreEqual("refresh_token", form["grant_type"]);
            Assert.AreEqual("application", form["client_id"]);
            grants.Add(form["refresh_token"]);
            started.TrySetResult();
            await complete.Task.WaitAsync(ct);
            return TestHandler.Json("""{"access_token":"refreshed","refresh_token":"rotated","id_token":"identity","scope":"read write","expires_in":3600}""");
        }));
        var grant = new TokenGrant(new AccessToken("expired", DateTimeOffset.UnixEpoch)) { RefreshToken = "initial" };
        using var credential = new TokenGrantCredentials(grant, new OidcOptions(Issuer) { ClientId = "application", HttpClient = http });
        var context = new ClientContext();
        Task<AccessToken> first = credential.GetTokenAsync(context).AsTask();
        await started.Task.WaitAsync(TimeSpan.FromSeconds(5));
        Task<AccessToken> second = credential.GetTokenAsync(context).AsTask();
        using var cancellation = new CancellationTokenSource();
        Task<AccessToken> canceled = credential.GetTokenAsync(context, cancellation.Token).AsTask();
        cancellation.Cancel();
        await Assert.ThrowsAsync<OperationCanceledException>(() => canceled);
        complete.SetResult();
        Assert.AreSame(await first, await second);
        Assert.AreEqual("rotated", credential.Snapshot.RefreshToken);
        Assert.AreEqual("identity", credential.Snapshot.IdToken);
        Assert.HasCount(2, credential.Snapshot.Scopes);
        await credential.GetTokenAsync(new ClientContext(refreshLeeway: TimeSpan.FromHours(2)));
        CollectionAssert.AreEqual(ExpectedRefreshTokens, grants);
        Assert.AreEqual(1, discoveryCount);
    }

    [TestMethod]
    public async Task RejectsMismatchedDiscoveryIssuerBeforeExchange()
    {
        using var http = new HttpClient(new TestHandler((request, _) =>
        {
            Assert.AreEqual(HttpMethod.Get, request.Method);
            return Task.FromResult(TestHandler.Json("""{"issuer":"https://other.example.test","token_endpoint":"https://other.example.test/token"}"""));
        }));
        var grant = new TokenGrant(new AccessToken("expired", DateTimeOffset.UnixEpoch)) { RefreshToken = "old" };
        using var credential = new TokenGrantCredentials(grant, new OidcOptions(Issuer) { ClientId = "application", HttpClient = http });
        await Assert.ThrowsExactlyAsync<AuthenticationException>(() => credential.GetTokenAsync(new ClientContext()).AsTask());
    }

    [TestMethod]
    public async Task WorkloadGrantRereadsTheProjectedTokenAndCanRecoverAfterRejection()
    {
        var path = Path.GetTempFileName();
        try
        {
            var subjects = new List<string?>();
            using var http = new HttpClient(new TestHandler(async (request, ct) =>
            {
                NameValueCollection form = HttpUtility.ParseQueryString(await request.Content!.ReadAsStringAsync(ct));
                Assert.AreEqual("urn:onenexus:params:oauth:grant-type:workload-identity", form["grant_type"]);
                Assert.AreEqual("urn:ietf:params:oauth:token-type:jwt", form["subject_token_type"]);
                Assert.AreEqual("service", form["audience"]);
                subjects.Add(form["subject_token"]);
                return subjects.Count == 1
                    ? TestHandler.Json("""{"error":"invalid_grant"}""", HttpStatusCode.BadRequest)
                    : TestHandler.Json("""{"access_token":"service-token","token_type":"Bearer","expires_in":3600}""");
            }));
            using var credential = new WorkloadIdentityFileCredentials(new OidcOptions(Issuer) { TokenEndpoint = Endpoint, Audience = "service", HttpClient = http }, path);
            await File.WriteAllTextAsync(path, " first\n");
            await Assert.ThrowsExactlyAsync<AuthenticationException>(() => credential.GetTokenAsync(new ClientContext()).AsTask());
            await File.WriteAllTextAsync(path, "second\n");
            Assert.AreEqual("service-token", (await credential.GetTokenAsync(new ClientContext())).Value);
            CollectionAssert.AreEqual(ExpectedSubjects, subjects);
        }
        finally
        {
            File.Delete(path);
        }
    }

    [TestMethod]
    public async Task PrivateKeyAssertionIsSignedForTheIssuer()
    {
        using var rsa = RSA.Create(2048);
        var key = new RsaSecurityKey(rsa) { KeyId = "test-key" };
        using var http = new HttpClient(new TestHandler(async (request, ct) =>
        {
            NameValueCollection form = HttpUtility.ParseQueryString(await request.Content!.ReadAsStringAsync(ct));
            Assert.AreEqual("client_credentials", form["grant_type"]);
            Assert.AreEqual("urn:ietf:params:oauth:client-assertion-type:jwt-bearer", form["client_assertion_type"]);
            Assert.AreEqual("api", form["scope"]);
            var handler = new JsonWebTokenHandler();
            TokenValidationResult valid = await handler.ValidateTokenAsync(form["client_assertion"], new TokenValidationParameters
            {
                ValidIssuer = "application",
                ValidAudience = Issuer.OriginalString,
                IssuerSigningKey = key,
                ValidTypes = ["client-authentication+jwt"],
                ValidAlgorithms = ["RS256"],
            });
            Assert.IsTrue(valid.IsValid);
            var assertion = (JsonWebToken)valid.SecurityToken;
            Assert.AreEqual("application", assertion.Subject);
            Assert.AreEqual(key.KeyId, assertion.Kid);
            Assert.IsFalse(string.IsNullOrWhiteSpace(assertion.Id));
            return TestHandler.Json("""{"access_token":"minted","expires_in":3600}""");
        }));
        using var credential = new PrivateKeyJwtCredentials(new OidcOptions(Issuer)
        {
            ClientId = "application", Scope = "api", TokenEndpoint = Endpoint, HttpClient = http,
        }, new SigningCredentials(key, SecurityAlgorithms.RsaSha256));
        Assert.AreEqual("minted", (await credential.GetTokenAsync(new ClientContext())).Value);
    }
}
