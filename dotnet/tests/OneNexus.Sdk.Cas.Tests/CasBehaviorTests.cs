using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Net;
using System.Net.Http;
using System.Text.Json;
using System.Text.Json.Nodes;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.IdentityModel.Tokens;
using Microsoft.VisualStudio.TestTools.UnitTesting;
using OneNexus.Sdk.Cas;
using OneNexus.Sdk.Cas.Generated.Models;
using OneNexus.Sdk.Core;
using OneNexus.Sdk.Tests;

namespace OneNexus.Sdk.Cas.Tests;

[TestClass]
public sealed class CasBehaviorTests
{
    private const string Region = "https://auth.eu-1.example.test";
    private static string Routed(string issuer) => "header." + Base64UrlEncoder.Encode(JsonSerializer.Serialize(new { iss = issuer })) + ".signature";

    [TestMethod]
    public async Task RoutedRetriesPinOriginAndToken()
    {
        var hosts = new List<Uri?>();
        var token = Routed(Region);
        var credentials = new CountingCredentials(token);
        using var http = new HttpClient(new TestHandler((req, _) =>
        {
            hosts.Add(req.RequestUri);
            Assert.AreEqual(token, req.Headers.Authorization?.Parameter);
            return Task.FromResult(hosts.Count == 1 ? new HttpResponseMessage(HttpStatusCode.ServiceUnavailable) : TestHandler.Json("{}"));
        }));
        using var client = new CasClient(WireTests.Origin, credentials, new SdkClientOptions { HttpClient = http, MaxRetryDelay = TimeSpan.Zero });
        await client.AssumeS3RoleAsync(new AssumeS3RoleRequest());
        Assert.HasCount(2, hosts);
        Assert.IsTrue(hosts.All(x => x == new Uri(Region + "/api/AssumeS3Role")));
        Assert.AreEqual(1, credentials.Calls);
    }

    [TestMethod]
    [DataRow("https://auth.eu-1.example.test.other.test")]
    [DataRow("https://auth.one.two.example.test")]
    [DataRow("http://auth.eu-1.example.test")]
    [DataRow("https://auth.eu-1.example.test:444")]
    [DataRow("https://auth.eu-1.example.test/path")]
    [DataRow("https://user@auth.eu-1.example.test")]
    public void RejectsUntrustedIssuer(string issuer) =>
        Assert.ThrowsExactly<ArgumentException>(() => CasRouting.ResolveAssumeS3RoleBaseUrl(WireTests.Origin, Routed(issuer)));

    [TestMethod]
    public async Task RoutedUnauthorizedStopsAfterOneAttempt()
    {
        var attempts = 0;
        using var http = new HttpClient(new TestHandler((_, _) =>
        {
            attempts++;
            return Task.FromResult(new HttpResponseMessage(HttpStatusCode.Unauthorized));
        }));
        using var client = new CasClient(WireTests.Origin, WireTests.Token(Routed(Region)), new SdkClientOptions { HttpClient = http });
        await Assert.ThrowsExactlyAsync<HttpRequestException>(() => client.AssumeS3RoleAsync(new AssumeS3RoleRequest()));
        Assert.AreEqual(1, attempts);
    }

    [TestMethod]
    public async Task OrdinaryUnauthorizedRechecksCredentialsWithObservedServerTime()
    {
        DateTimeOffset serverTime = DateTimeOffset.UtcNow.AddMinutes(5);
        var attempts = 0;
        var credentials = new CountingCredentials("fresh");
        using var http = new HttpClient(new TestHandler((_, _) =>
        {
            attempts++;
            HttpResponseMessage response = attempts == 1 ? new HttpResponseMessage(HttpStatusCode.Unauthorized) : TestHandler.Json("{}");
            response.Headers.Date = serverTime;
            return Task.FromResult(response);
        }));
        using var client = new CasClient(WireTests.Origin, credentials, new SdkClientOptions { HttpClient = http, MaxRetryDelay = TimeSpan.Zero });
        await client.ListUsersAsync();
        Assert.AreEqual(2, credentials.Calls);
        Assert.IsTrue((credentials.ObservedTime - serverTime).Duration() < TimeSpan.FromSeconds(2));
    }

    [TestMethod]
    public async Task ClassifiesProblemTypeAndPreservesFieldErrors()
    {
        const string problem = """{"type":"https://onenexus.cloud/errors/failed-precondition","detail":"stale","errors":{"name":["required"]}}""";
        using var http = new HttpClient(new TestHandler((_, _) =>
            Task.FromResult(TestHandler.Json(problem, HttpStatusCode.Conflict, "application/problem+json"))));
        using var client = new CasClient(WireTests.Origin, WireTests.Token(), new SdkClientOptions { HttpClient = http });
        PlatformException error = await Assert.ThrowsExactlyAsync<PlatformException>(() => client.ListUsersAsync());
        Assert.AreEqual("failed_precondition", error.Code);
        Assert.AreEqual(HttpStatusCode.Conflict, error.StatusCode);
        Assert.AreEqual("stale", error.Detail);
        Assert.AreEqual("required", error.FieldErrors["name"].Single());
    }

    [TestMethod]
    public async Task NestedPolicySurvivesReadAndWrite()
    {
        const string document = """{"statements":[{"nested":{"values":[0,true,null]}}]}""";
        using var http = new HttpClient(new TestHandler(async (request, ct) =>
        {
            if (request.RequestUri?.AbsolutePath == "/api/GetPolicy")
            {
                return TestHandler.Json("{\"policy\":{\"document\":" + document + "}}");
            }
            var body = await request.Content!.ReadAsStringAsync(ct);
            Assert.IsTrue(JsonNode.DeepEquals(JsonNode.Parse(document), JsonNode.Parse(body)?["document"]));
            return TestHandler.Json("{}");
        }));
        using var client = new CasClient(WireTests.Origin, WireTests.Token(), new SdkClientOptions { HttpClient = http });
        GetPolicyResponse read = await client.GetPolicyAsync(new GetPolicyRequest { Name = "example" });
        await client.PublishPolicyAsync(new PublishPolicyRequest { Name = "example", Document = read.Policy?.Document });
    }

    [TestMethod]
    public async Task RejectsMissingRequiredResponseAndHonorsCancellation()
    {
        using var http = new HttpClient(new TestHandler((_, _) => Task.FromResult(new HttpResponseMessage(HttpStatusCode.NoContent))));
        using var client = new CasClient(WireTests.Origin, WireTests.Token(), new SdkClientOptions { HttpClient = http });
        await Assert.ThrowsExactlyAsync<InvalidDataException>(() => client.ListUsersAsync());
        await Assert.ThrowsAsync<OperationCanceledException>(() => client.ListUsersAsync(cancellationToken: new CancellationToken(true)));
    }

    private sealed class CountingCredentials : IAccessTokenCredential
    {
        private readonly string _value;

        internal CountingCredentials(string value) => _value = value;
        internal int Calls { get; private set; }
        internal DateTimeOffset ObservedTime { get; private set; }

        public ValueTask<AccessToken> GetTokenAsync(ClientContext context, CancellationToken cancellationToken = default)
        {
            Calls++;
            ObservedTime = context.UtcNow;
            return ValueTask.FromResult(new AccessToken(_value, ObservedTime.AddHours(1)));
        }
    }
}
