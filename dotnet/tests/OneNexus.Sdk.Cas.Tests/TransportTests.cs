using System;
using System.Net;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Threading.Tasks;
using Microsoft.VisualStudio.TestTools.UnitTesting;
using OneNexus.Sdk.Cas.Models;
using OneNexus.Sdk.Core;
using OneNexus.Sdk.Tests;

namespace OneNexus.Sdk.Cas.Tests;

[TestClass]
public sealed class TransportTests
{
    [TestMethod]
    public async Task ReturnsOriginalUnauthorizedWhenTokenIsUnchanged()
    {
        var attempts = 0;
        using var http = new HttpClient(new TestHandler((_, _) =>
        {
            attempts++;
            return Task.FromResult(TestHandler.Json("""{"detail":"rejected"}""", HttpStatusCode.Unauthorized, "application/problem+json"));
        }));
        using var client = new CasClient(WireTests.Origin, WireTests.Token(), new SdkClientOptions { HttpClient = http });
        PlatformException error = await Assert.ThrowsExactlyAsync<PlatformException>(() => client.ListUsersAsync());
        Assert.AreEqual(HttpStatusCode.Unauthorized, error.StatusCode);
        Assert.AreEqual("rejected", error.Detail);
        Assert.AreEqual(1, attempts);
    }

    [TestMethod]
    [DataRow(true, HttpStatusCode.TooManyRequests)]
    [DataRow(false, HttpStatusCode.ServiceUnavailable)]
    public async Task SurfacesRetryAfterOutsideDelayBudget(bool absoluteDate, HttpStatusCode status)
    {
        var attempts = 0;
        var serverTime = DateTimeOffset.FromUnixTimeSeconds(1800000000);
        using var http = new HttpClient(new TestHandler((_, _) =>
        {
            attempts++;
            HttpResponseMessage response = TestHandler.Json("""{"title":"try later"}""", status, "application/problem+json");
            response.Headers.Date = serverTime;
            response.Headers.RetryAfter = absoluteDate
                ? new RetryConditionHeaderValue(serverTime.AddSeconds(60))
                : new RetryConditionHeaderValue(TimeSpan.FromSeconds(60));
            return Task.FromResult(response);
        }));
        using var client = new CasClient(WireTests.Origin, WireTests.Token(), new SdkClientOptions { HttpClient = http, MaxRetryDelay = TimeSpan.Zero });
        PlatformException error = await Assert.ThrowsExactlyAsync<PlatformException>(() => client.ListUsersAsync());
        Assert.AreEqual(status, error.StatusCode);
        Assert.AreEqual("try later", error.Message);
        Assert.AreEqual(1, attempts);
    }

    [TestMethod]
    public async Task TimeoutIncludesServerRequestedDelay()
    {
        var attempts = 0;
        using var http = new HttpClient(new TestHandler((_, _) =>
        {
            attempts++;
            var response = new HttpResponseMessage(HttpStatusCode.TooManyRequests);
            response.Headers.RetryAfter = new RetryConditionHeaderValue(TimeSpan.FromSeconds(5));
            return Task.FromResult(response);
        }));
        using var client = new CasClient(WireTests.Origin, WireTests.Token(), new SdkClientOptions { HttpClient = http, Timeout = TimeSpan.FromMilliseconds(250) });
        await Assert.ThrowsAsync<OperationCanceledException>(() => client.ListUsersAsync());
        Assert.AreEqual(1, attempts);
    }

    [TestMethod]
    public async Task NetworkFailureAndTransientResponsesShareRetryBudget()
    {
        var attempts = 0;
        using var http = new HttpClient(new TestHandler((_, _) =>
        {
            if (++attempts == 1)
            {
                throw new HttpRequestException("Connection reset.");
            }
            var response = new HttpResponseMessage(HttpStatusCode.ServiceUnavailable);
            response.Headers.RetryAfter = new RetryConditionHeaderValue(TimeSpan.Zero);
            return Task.FromResult(response);
        }));
        using var client = new CasClient(WireTests.Origin, WireTests.Token(), new SdkClientOptions { HttpClient = http, MaxRetryDelay = TimeSpan.Zero });
        HttpRequestException error = await Assert.ThrowsExactlyAsync<HttpRequestException>(() => client.ListUsersAsync());
        Assert.AreEqual(HttpStatusCode.ServiceUnavailable, error.StatusCode);
        Assert.AreEqual(3, attempts);
    }

    [TestMethod]
    public void RestrictsCleartextServiceAndIssuerUrlsToLoopback()
    {
        var remote = new Uri("http://cas.example.test");
        Assert.ThrowsExactly<ArgumentException>(() => new CasClient(remote, WireTests.Token()));
        Assert.ThrowsExactly<ArgumentException>(() => new OidcOptions(remote));
        var loopback = new Uri("http://127.0.0.1:8080");
        using var local = new CasClient(loopback, WireTests.Token());
        Assert.AreEqual(loopback, new OidcOptions(loopback).Issuer);
    }

    [TestMethod]
    [DataRow("too-short")]
    [DataRow("1234567890123456!")]
    public async Task RejectsInvalidIdempotencyKeyBeforeSending(string key)
    {
        using var http = new HttpClient(new TestHandler((_, _) => throw new AssertFailedException("Unexpected HTTP request.")));
        using var client = new CasClient(WireTests.Origin, WireTests.Token(), new SdkClientOptions { HttpClient = http });
        await Assert.ThrowsExactlyAsync<ArgumentException>(() => client.PublishPolicyAsync(new PublishPolicyRequest(), key));
    }
}
