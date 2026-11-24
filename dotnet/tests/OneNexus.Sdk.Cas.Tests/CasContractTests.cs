using System;
using System.Collections.Generic;
using System.Net.Http;
using System.Text.Json.Nodes;
using System.Threading.Tasks;
using Microsoft.VisualStudio.TestTools.UnitTesting;
using OneNexus.Sdk.Cas;
using OneNexus.Sdk.Core;
using OneNexus.Sdk.Tests;

namespace OneNexus.Sdk.Cas.Tests;

[TestClass]
public sealed class CasContractTests
{
    public static IEnumerable<object[]> Operations => WireTests.Operations("cas");

    public static IEnumerable<object[]> PagedOperations => WireTests.PagedOperations("cas", ["after", "limit"], ["items", "after"]);

    [TestMethod]
    [DynamicData(nameof(Operations))]
    public async Task SendsContractRequest(string operation, string path, bool keyed, bool noContent) =>
        await WireTests.ExerciseAsync(options => new CasClient(WireTests.Origin, WireTests.Token(), options), operation, path, keyed, noContent);

    // Every list paged by cursor has a ListAll method that follows the cursor and stops when a page has none.
    [TestMethod]
    [DynamicData(nameof(PagedOperations))]
    public async Task ListAllFollowsEveryCursor(string path, string method, int limit)
    {
        var bodies = new List<JsonNode>();
        using var http = new HttpClient(new TestHandler(async (request, ct) =>
        {
            Assert.AreEqual(new Uri(WireTests.Origin, path), request.RequestUri);
            bodies.Add(JsonNode.Parse(await request.Content!.ReadAsStringAsync(ct))!);
            return TestHandler.Json(bodies.Count == 1 ? """{"items":[{},{}],"after":"next"}""" : """{"items":[{}]}""");
        }));
        using var client = new CasClient(WireTests.Origin, WireTests.Token(), new SdkClientOptions { HttpClient = http });
        Assert.AreEqual(3, await WireTests.CountAllAsync(client, method));
        Assert.HasCount(2, bodies);
        Assert.AreEqual(limit, (int)bodies[0]["limit"]!);
        Assert.IsNull(bodies[0]["after"]);
        Assert.AreEqual("next", (string?)bodies[1]["after"]);
    }
}
