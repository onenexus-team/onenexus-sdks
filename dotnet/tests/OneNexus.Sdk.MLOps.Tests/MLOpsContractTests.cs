using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Net;
using System.Net.Http;
using System.Reflection;
using System.Text.Json;
using System.Text.Json.Nodes;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.VisualStudio.TestTools.UnitTesting;
using OneNexus.Sdk.Core;
using OneNexus.Sdk.MLOps.Models;
using OneNexus.Sdk.Tests;

namespace OneNexus.Sdk.MLOps.Tests;

[TestClass]
public sealed class MLOpsContractTests
{
    private static readonly string[] ReadPrefixes = ["Get", "List", "Resolve", "Validate"];
    private static readonly Uri Origin = new Uri("https://mlops.example.test");

    public static IEnumerable<object[]> Operations
    {
        get
        {
            using var spec = JsonDocument.Parse(File.ReadAllBytes(Path.Combine(AppContext.BaseDirectory, "contracts", "mlops.json")));
            foreach (JsonProperty path in spec.RootElement.GetProperty("paths").EnumerateObject())
            {
                JsonProperty method = path.Value.EnumerateObject().Single();
                int[] statuses = [.. method.Value.GetProperty("responses").EnumerateObject()
                    .Where(response => response.Name.StartsWith('2')).Select(response => response.Name)
                    .Select(code => int.Parse(code, System.Globalization.CultureInfo.InvariantCulture))];
                yield return [path.Name, method.Name, statuses];
            }
        }
    }

    [TestMethod]
    [DynamicData(nameof(Operations))]
    public async Task SendsPublicOperation(string path, string verb, int[] statuses)
    {
        var name = path switch
        {
            "/v1/models" => "ListOpenAIModels",
            "/api/v1/health" => "GetHealth",
            "/api/v1/composer-configs" => "GetComposerConfigs",
            _ => path.Split('/')[^1],
        };
        var platformKey = name is "Fetch" or "Search" or "GetComposerConfigs" or "ListOpenAIModels";
        var anonymous = name is "GetHealth" or "ValidateInferenceKey";
        var singleAttempt = name is "Search" or "Fetch" or "InvokeInferencePublicEndpoint";
        var isRead = verb == "get" || ReadPrefixes.Any(prefix => name.StartsWith(prefix, StringComparison.Ordinal));
        var keyed = !isRead && !singleAttempt;
        MethodInfo[] methods = [.. typeof(MLOpsClient).GetMethods().Where(m => m.Name == name + "Async")];
        MethodInfo method = methods.Single(m => m.GetParameters().All(p => p.Name != "idempotencyKey"));
        var observedKeys = new List<string?>();
        var bodies = new List<string?>();
        var status = 0;
        var retry = !singleAttempt;
        using var http = new HttpClient(new TestHandler(async (request, ct) =>
        {
            Assert.AreEqual(verb.ToUpperInvariant(), request.Method.Method);
            Assert.AreEqual(new Uri(Origin, path), request.RequestUri);
            Assert.AreEqual(anonymous ? null : platformKey ? "platform-key" : "cas-token", request.Headers.Authorization?.Parameter);
            Assert.IsFalse(request.Headers.Contains("X-Nx1-Idempotency-Key"));
            observedKeys.Add(request.Headers.TryGetValues("Idempotency-Key", out IEnumerable<string>? values) ? values.Single() : null);
            bodies.Add(request.Content is null ? null : await request.Content.ReadAsStringAsync(ct));
            Assert.AreEqual(verb == "post", request.Content is not null);
            if (retry)
            {
                retry = false;
                return new HttpResponseMessage(HttpStatusCode.ServiceUnavailable);
            }
            return status == 204 ? new HttpResponseMessage(HttpStatusCode.NoContent) : TestHandler.Json("{}", (HttpStatusCode)status);
        }));
        TokenGrantCredentials? credentials = anonymous || platformKey ? null : new TokenGrantCredentials(new AccessToken("cas-token", DateTimeOffset.UtcNow.AddHours(1)));
        using var client = new MLOpsClient(Origin, credentials, new SdkClientOptions { HttpClient = http, MaxRetryDelay = TimeSpan.Zero });
        object?[] args = [.. method.GetParameters().Select(p => p.Name switch
        {
            "platformApiKey" => "platform-key",
            "cancellationToken" => CancellationToken.None,
            "request" => Activator.CreateInstance(p.ParameterType),
            _ => throw new AssertFailedException($"Unexpected parameter {p.Name}."),
        })];
        Assert.AreEqual(keyed ? 2 : 1, methods.Length);
        foreach (var success in statuses)
        {
            status = success;
            var operation = (Task)method.Invoke(client, args)!;
            await operation;
            if (method.ReturnType.IsGenericType)
            {
                var result = method.ReturnType.GetProperty("Result")!.GetValue(operation);
                Assert.AreEqual(status == 204, result is null);
            }
            else
            {
                Assert.AreEqual(204, status);
            }
        }
        if (!singleAttempt)
        {
            Assert.AreEqual(bodies[0], bodies[1]);
        }
        if (keyed)
        {
            Assert.IsTrue(Guid.TryParse(observedKeys[0], out _));
            Assert.AreEqual(observedKeys[0], observedKeys[1]);
            MethodInfo replay = methods.Single(m => m.GetParameters().Any(p => p.Name == "idempotencyKey"));
            object?[] replayArgs = [.. args[..^1], "explicit/key", CancellationToken.None];
            await (Task)replay.Invoke(client, replayArgs)!;
            Assert.AreEqual("explicit/key", observedKeys[^1]);
        }
        else
        {
            Assert.IsTrue(observedKeys.TrueForAll(key => key is null));
        }
    }

    [TestMethod]
    public async Task RoundTripsRunOutputUnionAndDatasetPage()
    {
        using var http = new HttpClient(new TestHandler(async (request, ct) =>
        {
            using var body = JsonDocument.Parse(await request.Content!.ReadAsStringAsync(ct));
            if (request.RequestUri?.AbsolutePath == "/api/v1/Training/CreateRun")
            {
                JsonElement output = body.RootElement.GetProperty("output_model");
                Assert.AreEqual("new", output.GetProperty("type").GetString());
                Assert.AreEqual("next", output.GetProperty("model_name").GetString());
                Assert.AreEqual(4, body.RootElement.GetProperty("hyperparameters").GetProperty("epochs").GetInt32());
                return TestHandler.Json("""{"data":{"status":"queued"}}""", HttpStatusCode.Accepted);
            }
            Assert.AreEqual("training", body.RootElement.GetProperty("name").GetString());
            Assert.AreEqual(2, body.RootElement.GetProperty("page").GetInt32());
            return TestHandler.Json("""{"items":[{"name":"training"}],"total_pages":3}""");
        }));
        var credentials = new TokenGrantCredentials(new AccessToken("cas", DateTimeOffset.UtcNow.AddHours(1)));
        using var client = new MLOpsClient(Origin, credentials, new SdkClientOptions { HttpClient = http });
        var request = new RpcCreateRunRequest
        {
            OutputModel = new RpcCreateRunRequest.RpcCreateRunRequest_output_model
            {
                NewRunOutputModelRequest = new NewRunOutputModelRequest { Type = "new", ModelName = "next", ModelVersionName = "v1" },
            },
            Hyperparameters = new RpcCreateRunRequest_hyperparameters { AdditionalData = { ["epochs"] = 4 } },
        };
        Response_TrainingActionResponse_ run = await client.CreateRunAsync(request);
        Assert.AreEqual("queued", run.Data?.Status);
        ListResponse_DatasetSummaryResponse_ page = await client.ListDatasetsAsync(new RpcListDatasetsRequest { Name = "training", Page = 2 });
        Assert.AreEqual(3, page.TotalPages);
        Assert.AreEqual("training", page.Items?.Single().Name);
    }

    [TestMethod]
    public async Task RejectsMissingControlPlaneCredentialsAndInvalidReplayKey()
    {
        using var http = new HttpClient(new TestHandler((_, _) => throw new AssertFailedException("Unexpected network request.")));
        using var client = new MLOpsClient(Origin, options: new SdkClientOptions { HttpClient = http });
        await Assert.ThrowsExactlyAsync<InvalidOperationException>(() => client.ListDatasetsAsync());
        await Assert.ThrowsExactlyAsync<ArgumentException>(() => client.CreateDatasetAsync(new RpcCreateDatasetRequest(), "invalid key"));
        await Assert.ThrowsExactlyAsync<ArgumentException>(() => client.ListOpenAIModelsAsync("invalid key"));
    }

    [TestMethod]
    public async Task RaisesPlatformExceptionForServiceProblem()
    {
        using var http = new HttpClient(new TestHandler((_, _) =>
        {
            // The body shape MLOps returns, including its snake_case trace_id and list-shaped errors.
            HttpResponseMessage response = TestHandler.Json(
                """{"type":"https://api-mlops.onenexus.cloud/problems/validation-failed","title":"Validation failed","status":422,"detail":"Invalid dataset","instance":"urn:onenexus:request:example","trace_id":"de95291a152c67a8f1eb94049b6f85cd","errors":[{"field":"name","code":"missing","message":"required"},{"field":"name","code":"too_short","message":"too short"},{"code":"conflict","message":"whole request"}]}""",
                HttpStatusCode.UnprocessableEntity, "application/problem+json");
            response.Headers.Add("X-Request-ID", "example");
            return Task.FromResult(response);
        }));
        using var client = new MLOpsClient(Origin, new TokenGrantCredentials(new AccessToken("cas", DateTimeOffset.UtcNow.AddHours(1))),
            new SdkClientOptions { HttpClient = http });
        PlatformException error = await Assert.ThrowsExactlyAsync<PlatformException>(() => client.CreateDatasetAsync(new RpcCreateDatasetRequest()));
        Assert.AreEqual(HttpStatusCode.UnprocessableEntity, error.StatusCode);
        Assert.AreEqual("https://api-mlops.onenexus.cloud/problems/validation-failed", error.ProblemType);
        Assert.AreEqual("Invalid dataset", error.Detail);
        Assert.AreEqual("example", error.RequestId);
        Assert.AreEqual("de95291a152c67a8f1eb94049b6f85cd", error.TraceId);
        Assert.AreEqual("required|too short", string.Join('|', error.FieldErrors["name"]));
        Assert.AreEqual("whole request", error.FieldErrors[""].Single());
    }

    public static IEnumerable<object[]> PagedOperations => WireTests.PagedOperations("mlops", ["page", "limit"], ["items", "total_pages"]);

    // Every list paged by page number has a ListAll method that reads each page in turn.
    [TestMethod]
    [DynamicData(nameof(PagedOperations))]
    public async Task ListAllReadsEveryPage(string path, string method, int limit)
    {
        var pages = new List<int>();
        using var http = new HttpClient(new TestHandler(async (request, ct) =>
        {
            Assert.AreEqual(new Uri(Origin, path), request.RequestUri);
            JsonNode body = JsonNode.Parse(await request.Content!.ReadAsStringAsync(ct))!;
            Assert.AreEqual(limit, (int?)body["limit"] ?? 0);
            pages.Add((int)body["page"]!);
            return TestHandler.Json("""{"items":[{}],"total_pages":2}""");
        }));
        using var client = new MLOpsClient(Origin, new TokenGrantCredentials(new AccessToken("cas", DateTimeOffset.UtcNow.AddHours(1))),
            new SdkClientOptions { HttpClient = http });
        Assert.AreEqual(2, await WireTests.CountAllAsync(client, method));
        Assert.AreEqual("1,2", string.Join(',', pages));
    }

    [TestMethod]
    [DataRow(3, 4, 3, 3)]
    [DataRow(0, 1, 1, 0)]
    [DataRow(1, 1, 1, 0)]
    [DataRow(3, 2, 2, 1)]
    public async Task ListAllStopsAtTheLastPageOrAnEmptyPage(int totalPages, int firstEmptyPage, int requests, int datasets)
    {
        var bodies = new List<JsonNode>();
        using var http = new HttpClient(new TestHandler(async (request, ct) =>
        {
            JsonNode body = JsonNode.Parse(await request.Content!.ReadAsStringAsync(ct))!;
            bodies.Add(body);
            var items = (int)body["page"]! < firstEmptyPage ? """[{"name":"training"}]""" : "[]";
            return TestHandler.Json($$"""{"items":{{items}},"total_pages":{{totalPages}}}""");
        }));
        using var client = new MLOpsClient(Origin, new TokenGrantCredentials(new AccessToken("cas", DateTimeOffset.UtcNow.AddHours(1))),
            new SdkClientOptions { HttpClient = http });
        var request = new RpcListDatasetsRequest { Name = "training", Page = 7, Limit = 5 };
        var names = new List<string?>();
        await foreach (DatasetSummaryResponse dataset in client.ListAllDatasetsAsync(request))
        {
            names.Add(dataset.Name);
        }

        Assert.HasCount(datasets, names);
        Assert.HasCount(requests, bodies);
        for (var i = 0; i < bodies.Count; i++)
        {
            Assert.AreEqual(i + 1, (int)bodies[i]["page"]!);
            Assert.AreEqual(100, (int)bodies[i]["limit"]!);
            Assert.AreEqual("training", (string?)bodies[i]["name"]);
        }
        Assert.AreEqual(("training", 7, 5), (request.Name, request.Page, request.Limit));
    }

    [TestMethod]
    [DataRow("invoke")]
    [DataRow("search")]
    [DataRow("fetch")]
    public async Task DoesNotReplayUnprotectedRequests(string operation)
    {
        var attempts = 0;
        using var http = new HttpClient(new TestHandler((_, _) =>
        {
            attempts++;
            throw new HttpRequestException("Connection lost.");
        }));
        var credentials = new TokenGrantCredentials(new AccessToken("cas", DateTimeOffset.UtcNow.AddHours(1)));
        using var client = new MLOpsClient(Origin, credentials, new SdkClientOptions { HttpClient = http, MaxRetryDelay = TimeSpan.Zero });
        await Assert.ThrowsExactlyAsync<HttpRequestException>(() => operation switch
        {
            "search" => client.SearchAsync(new SearchRequest { Query = "example" }, "platform"),
            "fetch" => client.FetchAsync(new FetchRequest(), "platform"),
            _ => client.InvokeInferencePublicEndpointAsync(new RpcInvokeInferencePublicEndpointRequest()),
        });
        Assert.AreEqual(1, attempts);
    }
}
