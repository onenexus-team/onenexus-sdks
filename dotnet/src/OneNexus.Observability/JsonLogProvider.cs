using System.Text;
using System.Text.Json;
using Microsoft.Extensions.Logging;
using OneNexus.LogContract;

namespace OneNexus.Observability;

[ProviderAlias("OneNexus")]
public sealed class JsonLogProvider : ILoggerProvider, ISupportExternalScope
{
    private readonly object gate = new();
    private readonly TextWriter writer;
    private readonly LogConfiguration configuration;
    private IExternalScopeProvider scopes = new LoggerExternalScopeProvider();
    private bool disposed;
    private long droppedRecords;
    public long DroppedRecords => Interlocked.Read(ref droppedRecords);

    public JsonLogProvider(LogConfiguration configuration, TextWriter? writer = null)
    {
        this.configuration = configuration;
        this.writer = writer ?? Console.Out;
    }

    public ILogger CreateLogger(string categoryName) => new Logger(this);
    public void SetScopeProvider(IExternalScopeProvider scopeProvider) => scopes = scopeProvider;

    public void Dispose()
    {
        lock (gate) disposed = true;
        // stdout and caller-owned writers are never closed by the provider.
    }

    private void Write<TState>(LogLevel level, TState state, Exception? exception, Func<TState, Exception?, string> formatter)
    {
        try
        {
            var record = new Dictionary<string, object?>
            {
                ["timestamp"] = checked((DateTime.UtcNow.Ticks - DateTime.UnixEpoch.Ticks) * 100),
                ["level"] = level switch
                {
                    LogLevel.Trace => "TRACE", LogLevel.Debug => "DEBUG", LogLevel.Information => "INFO",
                    LogLevel.Warning => "WARN", LogLevel.Error => "ERROR", LogLevel.Critical => "FATAL",
                    _ => throw new ArgumentException("invalid_log_level"),
                },
                ["service"] = configuration.Service,
                ["environment"] = configuration.Environment,
                ["region"] = configuration.Region,
                // Exception details are not implicitly serialized. Callers own safe message templates.
                ["message"] = formatter(state, null),
            };
            if (CorrelationContext.TraceId is { } trace) record["trace_id"] = trace;
            scopes.ForEachScope((scope, target) => AddFields(scope, target), record);
            AddFields(state, record);
            var json = JsonSerializer.SerializeToElement(record, Contract.JsonOptions);
            if (record.ContainsKey("event") != record.ContainsKey("outcome")) throw new ArgumentException("incomplete_event");
            var profile = !record.ContainsKey("trace_id") ? "common" : record.ContainsKey("event") ? "lifecycle" : "correlated";
            if (Contract.Validate(json, profile).Count != 0) throw new ArgumentException("invalid_log_record");
            var line = json.GetRawText();
            if (Encoding.UTF8.GetByteCount(line) > Contract.MaxRecordBytes) throw new ArgumentException("record_too_large");
            lock (gate)
            {
                if (disposed) throw new ObjectDisposedException(nameof(JsonLogProvider));
                writer.WriteLine(line);
            }
        }
        catch (Exception)
        {
            // Never log rejected data or a sink failure through this same logger.
            Interlocked.Increment(ref droppedRecords);
        }
    }

    private void AddFields(object? source, Dictionary<string, object?> target)
    {
        if (source is not IEnumerable<KeyValuePair<string, object?>> fields) return;
        foreach (var (key, value) in fields)
        {
            if (key is "event" or "outcome" || configuration.AllowedFields.Contains(key)) target[key] = value;
            // Arbitrary ILogger template/scope fields are ignored unless approved; common identity is protected.
        }
    }

    private sealed class Logger(JsonLogProvider owner) : ILogger
    {
        public IDisposable? BeginScope<TState>(TState state) where TState : notnull => owner.scopes.Push(state);
        public bool IsEnabled(LogLevel logLevel) => logLevel is >= LogLevel.Trace and < LogLevel.None;
        public void Log<TState>(LogLevel logLevel, EventId eventId, TState state, Exception? exception, Func<TState, Exception?, string> formatter)
        {
            if (IsEnabled(logLevel)) owner.Write(logLevel, state, exception, formatter);
        }
    }
}
