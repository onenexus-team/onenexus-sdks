using System.Collections.Generic;
using System.Threading.Tasks;
using Microsoft.VisualStudio.TestTools.UnitTesting;
using OneNexus.Sdk.Cas;
using OneNexus.Sdk.Tests;

namespace OneNexus.Sdk.Cas.Tests;

[TestClass]
public sealed class CasContractTests
{
    public static IEnumerable<object[]> Operations => WireTests.Operations("cas");

    [TestMethod]
    [DynamicData(nameof(Operations))]
    public async Task SendsContractRequest(string operation, string path, bool keyed, bool noContent) =>
        await WireTests.ExerciseAsync(options => new CasClient(WireTests.Origin, WireTests.Token(), options), operation, path, keyed, noContent);
}
