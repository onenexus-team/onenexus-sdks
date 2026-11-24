using System;
using System.Net;
using System.Net.Http;
using Microsoft.VisualStudio.TestTools.UnitTesting;

namespace OneNexus.Sdk.Core.Tests;

[TestClass]
public sealed class SdkClientOptionsTests
{
    [TestMethod]
    public void CreateDefaultHttpHandlerReturnsIndependentHandlersWithSdkDefaults()
    {
        using SocketsHttpHandler first = SdkClientOptions.CreateDefaultHttpHandler();
        using SocketsHttpHandler second = SdkClientOptions.CreateDefaultHttpHandler();

        Assert.AreNotSame(first, second);
        Assert.IsFalse(first.AllowAutoRedirect);
        Assert.IsFalse(first.UseCookies);
        Assert.AreEqual(DecompressionMethods.All, first.AutomaticDecompression);
        Assert.AreEqual(TimeSpan.FromMinutes(5), first.PooledConnectionLifetime);
    }
}
