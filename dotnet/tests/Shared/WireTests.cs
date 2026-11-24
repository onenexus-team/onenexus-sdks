using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Net;
using System.Net.Http;
using System.Reflection;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.VisualStudio.TestTools.UnitTesting;
using OneNexus.Sdk.Core;

namespace OneNexus.Sdk.Tests;

internal static class WireTests
{
    internal static readonly Uri Origin = new Uri("https://auth.example.test");

    internal static TokenGrantCredentials Token(string value = "opaque") => new TokenGrantCredentials(new AccessToken(value, DateTimeOffset.UtcNow.AddHours(1)));

    internal static IEnumerable<object[]> Operations(string service)
    {
        using var spec = JsonDocument.Parse(File.ReadAllBytes(Path.Combine(AppContext.BaseDirectory, "contracts", service + ".json")));
        foreach (JsonProperty path in spec.RootElement.GetProperty("paths").EnumerateObject())
        {
            JsonElement operation = path.Value.GetProperty("post");
            var keyed = operation.TryGetProperty("parameters", out JsonElement parameters) && parameters.EnumerateArray().Any(p =>
                p.GetProperty("name").GetString() == "X-Nx1-Idempotency-Key" && p.GetProperty("required").GetBoolean());
            yield return [operation.GetProperty("operationId").GetString()!, path.Name, keyed, operation.GetProperty("responses").TryGetProperty("204", out _)];
        }
    }

    // List operations whose request and 200 response declare the given paging fields, with the ListAll method expected
    // for each and the request's largest limit (0 when the contract sets none).
    internal static IEnumerable<object[]> PagedOperations(string service, string[] requestFields, string[] responseFields)
    {
        using var spec = JsonDocument.Parse(File.ReadAllBytes(Path.Combine(AppContext.BaseDirectory, "contracts", service + ".json")));
        JsonElement schemas = spec.RootElement.GetProperty("components").GetProperty("schemas");
        foreach (JsonProperty path in spec.RootElement.GetProperty("paths").EnumerateObject())
        {
            var name = path.Name.Split('/')[^1];
            JsonElement operation = path.Value.EnumerateObject().Single().Value;
            if (!name.StartsWith("List", StringComparison.Ordinal)
                || !operation.TryGetProperty("requestBody", out JsonElement body)
                || !operation.GetProperty("responses").TryGetProperty("200", out JsonElement ok)
                || Properties(schemas, body) is not JsonElement request
                || Properties(schemas, ok) is not JsonElement response
                || !requestFields.All(field => request.TryGetProperty(field, out _))
                || !responseFields.All(field => response.TryGetProperty(field, out _)))
            {
                continue;
            }
            var limit = request.GetProperty("limit").TryGetProperty("maximum", out JsonElement maximum) ? (int)maximum.GetDouble() : 0;
            yield return [path.Name, "ListAll" + name["List".Length..] + "Async", limit];
        }
    }

    // Enumerates a public ListAll method with a default request and counts the items it yields.
    internal static async Task<int> CountAllAsync(object client, string name)
    {
        MethodInfo method = client.GetType().GetMethod(name) ?? throw new AssertFailedException($"{client.GetType().Name} has no {name}.");
        object? request = Activator.CreateInstance(method.GetParameters()[0].ParameterType);
        var items = (IAsyncEnumerable<object>)method.Invoke(client, [request, CancellationToken.None])!;
        var count = 0;
        await foreach (object _ in items)
        {
            count++;
        }
        return count;
    }

    private static JsonElement? Properties(JsonElement schemas, JsonElement message) =>
        message.TryGetProperty("content", out JsonElement content)
        && content.TryGetProperty("application/json", out JsonElement json)
        && json.GetProperty("schema").TryGetProperty("$ref", out JsonElement reference)
        && schemas.GetProperty(reference.GetString()!.Split('/')[^1]).TryGetProperty("properties", out JsonElement properties)
            ? properties
            : null;

    // Drive the public method for every operation declared in the independent, committed contract.
    internal static async Task ExerciseAsync<T>(Func<SdkClientOptions, T> create, string operation, string path, bool keyed, bool noContent)
        where T : IDisposable
    {
        var keys = new List<string?>();
        var bodies = new List<string>();
        using var http = new HttpClient(new TestHandler(async (request, ct) =>
        {
            Assert.AreEqual(new Uri(Origin, path), request.RequestUri);
            Assert.AreEqual(HttpMethod.Post, request.Method);
            Assert.AreEqual("Bearer opaque", request.Headers.Authorization?.ToString());
            Assert.AreEqual("application/json", request.Content?.Headers.ContentType?.MediaType);
            keys.Add(request.Headers.TryGetValues("X-Nx1-Idempotency-Key", out IEnumerable<string>? values) ? values.Single() : null);
            bodies.Add(await request.Content!.ReadAsStringAsync(ct));
            if (keys.Count is 1 or 4)
            {
                return new HttpResponseMessage(HttpStatusCode.ServiceUnavailable);
            }
            return noContent ? new HttpResponseMessage(HttpStatusCode.NoContent) : TestHandler.Json("{}");
        }));
        using T client = create(new SdkClientOptions { HttpClient = http, MaxRetryDelay = TimeSpan.Zero });
        MethodInfo[] methods = [.. typeof(T).GetMethods().Where(m => m.Name == operation + "Async")];
        MethodInfo method = methods.Single(m => m.GetParameters().All(p => p.Name != "idempotencyKey"));
        ParameterInfo[] parameters = method.GetParameters();
        Assert.AreEqual(typeof(CancellationToken), parameters[^1].ParameterType);
        object?[] args = parameters.Length == 1 ? [CancellationToken.None] : [Activator.CreateInstance(parameters[0].ParameterType), CancellationToken.None];
        for (var i = 0; i < 2; i++)
        {
            await (Task)method.Invoke(client, args)!;
        }
        Assert.HasCount(3, keys);
        Assert.AreEqual(bodies[0], bodies[1]);
        if (parameters.Length == 1)
        {
            Assert.AreEqual("{}", bodies[0]);
        }
        if (keyed)
        {
            Assert.IsTrue(Guid.TryParseExact(keys[0], "D", out _));
            Assert.AreEqual(keys[0], keys[1]);
            Assert.AreNotEqual(keys[0], keys[2]);

            const string callerKey = "cli.operation_123-456";
            MethodInfo explicitKey = methods.Single(m => m.GetParameters().Any(p => p.Name == "idempotencyKey"));
            object?[] replay = [.. args[..^1], callerKey, CancellationToken.None];
            await (Task)explicitKey.Invoke(client, replay)!;
            await (Task)explicitKey.Invoke(client, replay)!;
            Assert.HasCount(6, keys);
            Assert.IsTrue(keys.Skip(3).All(key => key == callerKey));
            Assert.AreEqual(bodies[3], bodies[4]);
        }
        else
        {
            Assert.IsTrue(keys.TrueForAll(key => key is null));
        }
        Assert.AreEqual(noContent, method.ReturnType == typeof(Task));
    }
}
