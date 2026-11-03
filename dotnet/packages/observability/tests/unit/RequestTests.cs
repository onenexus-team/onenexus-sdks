using System.Text.Json;
using Microsoft.Extensions.Logging;
using Microsoft.VisualStudio.TestTools.UnitTesting;
using OneNexus.Observability.Rules;

namespace OneNexus.Observability.Tests;

[TestClass]
public sealed class RequestTests
{
    private static readonly string Tenant = new('1',32);
    private static readonly string Owner = $"nx1://test/{Tenant}/CAS/global/User/" + new string('2',32);

    [TestMethod]
    public void SharedRequestEmissions()
    {
        using var suite = JsonDocument.Parse(File.ReadAllBytes(Environment.GetEnvironmentVariable("ONENEXUS_LOGGING_SCENARIOS")!));
        foreach (var item in suite.RootElement.GetProperty("request_emission_cases").EnumerateArray())
        {
            using var output = new StringWriter();
            using var provider = new JsonLogProvider(new("request-test","development","test"),output);
            var logger = provider.CreateLogger("request");
            using (var receipt = RequestLogContext.Begin(item.GetProperty("id").GetString()!))
            {
                receipt.BindVerifiedIdentity(item.GetProperty("principal").GetString(),item.GetProperty("tenant").GetString());
                if (item.GetProperty("error").GetString() is { } error) receipt.SetError(error);
                logger.Log(LogLevel.Information, new EventId(), new Dictionary<string,object?> { ["principal_id"]="spoofed" }, null, (_,_)=>"Application event");
                var status = item.GetProperty("status");
                var fields=receipt.TerminalFields("POST","/items/{id}",status.ValueKind==JsonValueKind.Null?null:status.GetInt32(),1.5,item.GetProperty("interrupted").GetBoolean());
                logger.Log(LogLevel.Information,new EventId(),fields,null,(_,_)=>"Request finished");
            }
            logger.LogInformation("Outside request");
            var rows=output.ToString().Split('\n',StringSplitOptions.RemoveEmptyEntries).Select(line=>JsonDocument.Parse(line).RootElement.Clone()).ToArray();
            Assert.HasCount(3,rows);
            Assert.AreEqual(item.GetProperty("principal").GetString(),rows[0].GetProperty("principal_id").GetString());
            foreach(var expected in item.GetProperty("expected").EnumerateObject())
                Assert.IsTrue(JsonElement.DeepEquals(expected.Value, rows[1].GetProperty(expected.Name)),expected.Name);
            Assert.IsEmpty(Contract.Validate(rows[1],"request"));
            Assert.IsFalse(rows[1].TryGetProperty("trace_id",out _));
            Assert.IsFalse(rows[2].TryGetProperty("principal_id",out _));
            Assert.AreEqual(0L,provider.DroppedRecords);
        }
    }

    [TestMethod]
    public void EnforcesRequestProfileAtEmission()
    {
        using var output=new StringWriter();
        using var provider=new JsonLogProvider(new("request-test","development","test"),output);
        var logger=provider.CreateLogger("request");
        logger.Log(LogLevel.Information,new EventId(),new Dictionary<string,object?>{["request_event"]="completed"},null,(_,_)=>"Missing fields");
        using var receipt=RequestLogContext.Begin("request-1");
        logger.Log(LogLevel.Information,new EventId(),receipt.TerminalFields("GET","/",null,1),null,(_,_)=>"No observed status");
        Assert.AreEqual("",output.ToString());
        Assert.AreEqual(2L,provider.DroppedRecords);
    }

    [TestMethod]
    public void ValidatesIdentityAndClearsNestedContexts()
    {
        foreach(var invalid in new[]{"","x\n",new string('x',129)})
            Assert.Throws<ArgumentException>(()=>RequestLogContext.Begin(invalid));
        var outer=RequestLogContext.Begin("outer");
        outer.BindVerifiedIdentity(Owner,Tenant);
        using(var inner=RequestLogContext.Begin("inner")) Assert.IsNull(RequestLogContext.CurrentFields()["principal_id"]);
        Assert.AreEqual(Owner,RequestLogContext.CurrentFields()["principal_id"]);
        foreach(var pair in new[]{(Owner,new string('3',32)),("username",Tenant),(Owner,new string('0',32))})
        {
            outer.BindVerifiedIdentity(pair.Item1,pair.Item2);
            Assert.IsNull(outer.Fields()["principal_id"]);
        }
        Assert.Throws<ArgumentException>(()=>outer.SetError("secret message"));
        outer.Dispose(); outer.BindVerifiedIdentity(Owner,Tenant);outer.SetError("LATE");
        Assert.IsEmpty(outer.Fields());Assert.IsEmpty(RequestLogContext.CurrentFields());
        Assert.Throws<InvalidOperationException>(()=>outer.TerminalFields("GET","/",200,1));
    }

    [TestMethod]
    public async Task ConcurrentAndDetachedTasksCannotLeakIdentity()
    {
        await Task.WhenAll(Enumerable.Range(0,20).Select(async i=> {
            using var receipt=RequestLogContext.Begin($"request-{i}");
            receipt.BindVerifiedIdentity(Owner,Tenant);
            await Task.Yield();
            Assert.AreEqual($"request-{i}",RequestLogContext.CurrentFields()["request_id"]);
        }));
        var resume=new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
        Task<IReadOnlyDictionary<string,object?>> child;
        using(var receipt=RequestLogContext.Begin("detached"))
        {
            receipt.BindVerifiedIdentity(Owner,Tenant);
            child=Task.Run(async ()=> {await resume.Task;receipt.BindVerifiedIdentity(Owner,Tenant);return RequestLogContext.CurrentFields();});
        }
        resume.SetResult();
        Assert.IsEmpty(await child);
        try {using var receipt=RequestLogContext.Begin("failure");await Task.Yield();throw new OperationCanceledException();}
        catch(OperationCanceledException) { }
        Assert.IsEmpty(RequestLogContext.CurrentFields());
    }
}
