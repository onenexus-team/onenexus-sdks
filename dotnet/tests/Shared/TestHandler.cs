using System;
using System.Diagnostics.CodeAnalysis;
using System.Net;
using System.Net.Http;
using System.Text;
using System.Threading;
using System.Threading.Tasks;

namespace OneNexus.Sdk.Tests;

internal sealed class TestHandler : HttpMessageHandler
{
    private readonly Func<HttpRequestMessage, CancellationToken, Task<HttpResponseMessage>> _send;

    internal TestHandler(Func<HttpRequestMessage, CancellationToken, Task<HttpResponseMessage>> send) => _send = send;

    internal static HttpResponseMessage Json([StringSyntax(StringSyntaxAttribute.Json)] string json, HttpStatusCode status = HttpStatusCode.OK, string mediaType = "application/json") =>
        new HttpResponseMessage(status) { Content = new StringContent(json, Encoding.UTF8, mediaType) };

    protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken) => _send(request, cancellationToken);
}
