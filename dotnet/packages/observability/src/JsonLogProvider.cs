using System.Diagnostics;
using System.Text;
using System.Text.Json;
using Microsoft.Extensions.Logging;
using OneNexus.Observability.Rules;

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
    private const string ErrorTypeField = "error.type";
    private const string StacktraceField = "exception.stacktrace";
    private const string TruncatedField = "logging.truncated";
    private const string DroppedField = "logging.dropped_field_count";
    private const string TruncationMark = "\u2026";
    private static readonly UTF8Encoding StrictUtf8 = new(false, true);
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
            var (message, truncated) = Shorten(formatter(state, null), Contract.MaxMessageBytes);
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
                // The exception adds its type and frames below, never its message. Callers own safe message templates.
                ["message"] = message,
            };
            if (CorrelationContext.TraceId is { } trace) record["trace_id"] = trace;
            var draft = new Draft(record) { Truncated = truncated };
            scopes.ForEachScope((scope, target) => AddFields(scope, target), draft);
            AddFields(state, draft);
            foreach (var (key, value) in RequestLogContext.CurrentFields()) record[key] = value;
            if (exception is not null)
            {
                var (error, cut) = ErrorFields(exception);
                foreach (var (key, value) in error)
                    // A caller-supplied value wins; only the SDK's own stack can carry its cut flag.
                    if (record.TryAdd(key, value) && key == StacktraceField) draft.Truncated |= cut;
            }
            if (record.ContainsKey("event") != record.ContainsKey("outcome")) throw new ArgumentException("incomplete_event");
            var json = Fit(draft);
            var profile = record.ContainsKey("request_event") ? "request" : !record.ContainsKey("trace_id") ? "common" : record.ContainsKey("event") ? "lifecycle" : "correlated";
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

    private void AddFields(object? source, Draft draft)
    {
        if (source is not IEnumerable<KeyValuePair<string, object?>> fields) return;
        foreach (var (key, value) in fields)
        {
            if (key is "event" or "outcome") draft.Record[key] = value;
            else if ((RequestLogContext.FieldNames.Contains(key) || configuration.AllowedFields.Contains(key)) && TryFieldValue(key, value, out var emitted, out var cut))
            {
                draft.Record[key] = emitted;
                draft.Truncated |= cut;
                if (!RequestLogContext.FieldNames.Contains(key)) draft.Custom.Add(key);
            }
            // Unapproved, protected or unsupported fields are never emitted; common identity is protected. The template is metadata.
            else if (key != "{OriginalFormat}") draft.Dropped++;
        }
    }

    /// <summary>The value to emit and whether it was cut; false when it cannot be emitted.</summary>
    private static bool TryFieldValue(string key, object? value, out object? emitted, out bool cut)
    {
        emitted = value;
        cut = false;
        if (key == ErrorTypeField && !ValidErrorType(value)) return false;
        if (key == StacktraceField && value is not string { Length: > 0 }) return false;
        if (value is string text)
        {
            try { StrictUtf8.GetByteCount(text); }
            catch (EncoderFallbackException) { return false; } // Not valid Unicode, e.g. a lone surrogate.
            (emitted, cut) = Shorten(text, key == StacktraceField ? Contract.MaxStacktraceBytes : Contract.MaxFieldBytes);
            return true;
        }
        try { JsonSerializer.SerializeToUtf8Bytes(value, Contract.JsonOptions); } // Probe only; emitted as before.
        catch (Exception) { return false; } // Non-finite numbers and values System.Text.Json cannot serialise.
        return true;
    }

    private static bool ValidErrorType(object? value) => value is string { Length: > 0 } text &&
        text.EnumerateRunes().Count() <= Contract.MaxErrorTypeChars && !text.Any(char.IsWhiteSpace);

    /// <summary>Cut at a code-point boundary so the text plus the mark fits <paramref name="limit"/> UTF-8 bytes.</summary>
    private static (string Text, bool Cut) Shorten(string text, int limit)
    {
        if (text is null || Encoding.UTF8.GetByteCount(text) <= limit) return (text!, false);
        int budget = limit - Encoding.UTF8.GetByteCount(TruncationMark), size = 0, end = 0;
        foreach (var rune in text.EnumerateRunes())
        {
            if (size + rune.Utf8SequenceLength > budget) break;
            size += rune.Utf8SequenceLength;
            end += rune.Utf16SequenceLength;
        }
        return (text[..end] + TruncationMark, true);
    }

    /// <summary>Type and frames of an exception; never its message or argument values.</summary>
    private static (List<KeyValuePair<string, object?>> Fields, bool Cut) ErrorFields(Exception exception)
    {
        var type = exception.GetType();
        var name = type.FullName ?? type.Name;
        if (!ValidErrorType(name))
        {
            name = type.Name.Split('`')[0];
            name = name[..Math.Min(name.Length, Contract.MaxErrorTypeChars)];
        }
        var fields = new List<KeyValuePair<string, object?>> { new(ErrorTypeField, name) };
        var lines = new StackTrace(exception, true).GetFrames().Select(FrameLine).ToList();
        if (lines.Count == 0) return (fields, false);
        var (stack, cut) = Frames(lines);
        fields.Add(new(StacktraceField, stack));
        return (fields, cut);
    }

    private static string FrameLine(StackFrame frame)
    {
        var method = frame.GetMethod();
        var type = method?.DeclaringType;
        var owner = type?.FullName is { } full && !full.Any(char.IsWhiteSpace) ? full : type?.Name;
        var line = "at " + (owner is null ? "" : owner + ".") + (method?.Name ?? "<unknown>");
        return frame.GetFileName() is { } file ? $"{line} ({Path.GetFileName(file)}:{frame.GetFileLineNumber()})" : line;
    }

    /// <summary>Keep whole frames, innermost first, within the stack budget.</summary>
    private static (string Stack, bool Cut) Frames(List<string> lines)
    {
        var kept = new List<string>();
        var size = 0;
        foreach (var raw in lines)
        {
            var (line, cut) = Shorten(raw, Contract.MaxStacktraceBytes);
            var cost = Encoding.UTF8.GetByteCount(line) + (kept.Count > 0 ? 1 : 0);
            if (cut || size + cost > Contract.MaxStacktraceBytes) return (kept.Count > 0 ? string.Join('\n', kept) : line, true);
            kept.Add(line);
            size += cost;
        }
        return (string.Join('\n', kept), false);
    }

    /// <summary>Shorten the stack, then remove the largest custom fields, until the record fits.</summary>
    private static JsonElement Fit(Draft draft)
    {
        var record = draft.Record;
        while (true)
        {
            if (draft.Truncated) record[TruncatedField] = true;
            if (draft.Dropped > 0) record[DroppedField] = Math.Min(draft.Dropped, Contract.MaxDroppedFieldCount);
            var json = JsonSerializer.SerializeToElement(record, Contract.JsonOptions);
            if (Encoding.UTF8.GetByteCount(json.GetRawText()) <= Contract.MaxRecordBytes) return json;
            if (ShrinkStack(record))
            {
                draft.Truncated = true;
                continue;
            }
            var largest = draft.Custom.Where(record.ContainsKey)
                .OrderByDescending(k => Encoding.UTF8.GetByteCount(JsonSerializer.Serialize(new Dictionary<string, object?> { [k] = record[k] }, Contract.JsonOptions)))
                .ThenByDescending(k => k, StringComparer.Ordinal).FirstOrDefault();
            if (largest is null) return json; // Still too large: the size check drops it.
            record.Remove(largest);
            draft.Dropped++;
        }
    }

    /// <summary>Drop the outermost frame; remove the stack once one frame is left.</summary>
    private static bool ShrinkStack(Dictionary<string, object?> record)
    {
        if (record.GetValueOrDefault(StacktraceField) is not string stack) return false;
        var cut = stack.LastIndexOf('\n');
        if (cut >= 0) record[StacktraceField] = stack[..cut];
        else record.Remove(StacktraceField);
        return true;
    }

    private sealed class Draft(Dictionary<string, object?> record)
    {
        public Dictionary<string, object?> Record { get; } = record;
        public HashSet<string> Custom { get; } = new(StringComparer.Ordinal);
        public int Dropped { get; set; }
        public bool Truncated { get; set; }
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
