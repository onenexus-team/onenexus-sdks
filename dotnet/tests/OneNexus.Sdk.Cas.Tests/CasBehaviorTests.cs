using System;
using System.Buffers.Text;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Net;
using System.Net.Http;
using System.Text.Json;
using System.Text.Json.Nodes;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.VisualStudio.TestTools.UnitTesting;
using OneNexus.Sdk.Cas;
using OneNexus.Sdk.Cas.Models;
using OneNexus.Sdk.Core;
using OneNexus.Sdk.Tests;

namespace OneNexus.Sdk.Cas.Tests;

[TestClass]
public sealed class CasBehaviorTests
{
    private const string Region = "https://auth.eu-1.example.test";
    private static string Routed(string issuer) => "header." + Base64Url.EncodeToString(JsonSerializer.SerializeToUtf8Bytes(new { iss = issuer })) + ".signature";

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
    public async Task RejectsUntrustedIssuer(string issuer)
    {
        using var http = new HttpClient(new TestHandler((_, _) => throw new AssertFailedException("Unexpected HTTP request.")));
        using var client = new CasClient(WireTests.Origin, WireTests.Token(Routed(issuer)), new SdkClientOptions { HttpClient = http });
        await Assert.ThrowsExactlyAsync<ArgumentException>(() => client.AssumeS3RoleAsync(new AssumeS3RoleRequest()));
    }

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
        var credentials = new CountingCredentials("old", "fresh");
        using var http = new HttpClient(new TestHandler((request, _) =>
        {
            attempts++;
            Assert.AreEqual(attempts == 1 ? "old" : "fresh", request.Headers.Authorization?.Parameter);
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
    [DataRow("""{"title":"Conflict","requestId":"body-request","traceId":"body-trace"}""", "body-request", "body-trace")]
    [DataRow("""{"title":"Conflict","trace_id":"body-trace"}""", "header-request", "body-trace")]
    [DataRow("""{"title":"Conflict","errors":"not a field map"}""", "header-request", "header-trace")]
    public async Task ReadsProblemIdsFromBodyThenHeaders(string problem, string requestId, string traceId)
    {
        using var http = new HttpClient(new TestHandler((_, _) =>
        {
            HttpResponseMessage response = TestHandler.Json(problem, HttpStatusCode.Conflict, "application/problem+json");
            response.Headers.Add("X-Request-ID", "header-request");
            response.Headers.Add("X-Trace-Id", "header-trace");
            return Task.FromResult(response);
        }));
        using var client = new CasClient(WireTests.Origin, WireTests.Token(), new SdkClientOptions { HttpClient = http });
        PlatformException error = await Assert.ThrowsExactlyAsync<PlatformException>(() => client.ListUsersAsync());
        Assert.AreEqual("Conflict", error.Title);
        Assert.AreEqual(requestId, error.RequestId);
        Assert.AreEqual(traceId, error.TraceId);
        Assert.IsEmpty(error.FieldErrors);
    }

    [TestMethod]
    public async Task ListAllUsersPagesACopyOfTheRequest()
    {
        var bodies = new List<JsonNode>();
        using var http = new HttpClient(new TestHandler(async (request, ct) =>
        {
            bodies.Add(JsonNode.Parse(await request.Content!.ReadAsStringAsync(ct))!);
            // An empty page can still carry a cursor to the next one.
            return TestHandler.Json(bodies.Count % 2 == 1 ? """{"items":[],"after":"next"}""" : """{"items":[{"displayName":"An"}]}""");
        }));
        using var client = new CasClient(WireTests.Origin, WireTests.Token(), new SdkClientOptions { HttpClient = http });
        var request = new ListUsersRequest { Query = "an", Limit = 5, After = "stale", Before = "earlier" };
        IAsyncEnumerable<TenantUserSummary> users = client.ListAllUsersAsync(request);
        for (var run = 0; run < 2; run++)
        {
            var names = new List<string?>();
            await foreach (TenantUserSummary user in users)
            {
                names.Add(user.DisplayName);
            }
            Assert.AreEqual("An", names.Single());
        }

        Assert.HasCount(4, bodies);
        foreach (JsonNode body in bodies)
        {
            Assert.AreEqual("an", (string?)body["query"]);
            Assert.AreEqual(200, (int)body["limit"]!);
            Assert.IsNull(body["before"]);
        }
        Assert.IsNull(bodies[0]["after"]);
        Assert.AreEqual("next", (string?)bodies[1]["after"]);
        Assert.IsNull(bodies[2]["after"]);
        Assert.AreEqual(("an", 5, "stale", "earlier"), (request.Query, request.Limit, request.After, request.Before));
    }

    [TestMethod]
    public async Task ListAllUsersRejectsARepeatedCursor()
    {
        var calls = 0;
        using var http = new HttpClient(new TestHandler((_, _) =>
        {
            calls++;
            return Task.FromResult(TestHandler.Json("""{"items":[{}],"after":"same"}"""));
        }));
        using var client = new CasClient(WireTests.Origin, WireTests.Token(), new SdkClientOptions { HttpClient = http });
        await Assert.ThrowsExactlyAsync<InvalidDataException>(async () =>
        {
            await foreach (TenantUserSummary _ in client.ListAllUsersAsync())
            {
            }
        });
        Assert.AreEqual(2, calls);
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
        private readonly string[] _tokens;

        internal CountingCredentials(params string[] tokens) => _tokens = tokens;
        internal int Calls { get; private set; }
        internal DateTimeOffset ObservedTime { get; private set; }

        public ValueTask<AccessToken> GetTokenAsync(ClientContext context, CancellationToken cancellationToken = default)
        {
            Calls++;
            ObservedTime = context.UtcNow;
            return ValueTask.FromResult(new AccessToken(_tokens[Calls - 1], ObservedTime.AddHours(1)));
        }
    }
}
