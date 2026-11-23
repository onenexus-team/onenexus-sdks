using System.Collections.Generic;
using System.Net.Http;
using System.Threading.Tasks;
using Microsoft.VisualStudio.TestTools.UnitTesting;
using OneNexus.Sdk.Cas.Support;
using OneNexus.Sdk.Core;
using OneNexus.Sdk.Tests;

namespace OneNexus.Sdk.Cas.Support.Tests;

[TestClass]
public sealed class CasSupportContractTests
{
    [TestMethod]
    public async Task ListsTenantsWithoutFilters()
    {
        using var http = new HttpClient(new TestHandler(async (request, ct) =>
        {
            Assert.AreEqual("{}", await request.Content!.ReadAsStringAsync(ct));
            return TestHandler.Json("{}");
        }));
        using var client = new CasSupportClient(WireTests.Origin, WireTests.Token(), new SdkClientOptions { HttpClient = http });
        await client.ListTenantsAsync();
    }

    public static IEnumerable<object[]> Operations => WireTests.Operations("cas-support");

    [TestMethod]
    [DynamicData(nameof(Operations))]
    public async Task SendsContractRequest(string operation, string path, bool keyed, bool noContent) =>
        await WireTests.ExerciseAsync(options => new CasSupportClient(WireTests.Origin, WireTests.Token(), options), operation, path, keyed, noContent);
}
