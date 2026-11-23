using System.Collections.Generic;
using System.Threading.Tasks;
using Microsoft.VisualStudio.TestTools.UnitTesting;
using OneNexus.Sdk.Cas.Support;
using OneNexus.Sdk.Tests;

namespace OneNexus.Sdk.Cas.Support.Tests;

[TestClass]
public sealed class CasSupportContractTests
{
    public static IEnumerable<object[]> Operations => WireTests.Operations("cas-support");

    [TestMethod]
    [DynamicData(nameof(Operations))]
    public async Task SendsContractRequest(string operation, string path, bool keyed, bool noContent) =>
        await WireTests.ExerciseAsync(options => new CasSupportClient(WireTests.Origin, WireTests.Token(), options), operation, path, keyed, noContent);
}
