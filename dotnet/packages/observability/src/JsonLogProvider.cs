using System.Diagnostics;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Threading.Channels;
using Microsoft.Extensions.Logging;
using OneNexus.Observability.Rules;

namespace OneNexus.Observability;

/// <summary>The shared write counters (tests/logging write_model). Pending lines are accepted but not yet written.</summary>
public readonly record struct LogWriteStats(long Written, long Invalid, long QueueFull, long IoErrors, long Closed, long Pending);

/// <summary>
/// Contract-backed provider whose caller never waits on the output (design review F2).
/// Records are built and validated on the caller's thread, then queued (bounded, <see cref="QueueCapacity"/> lines)
/// for one background writer that owns every write. A full queue, a rejected record, a failed write and a write after
/// close are each counted, never thrown. <see cref="Dispose"/> drains for up to <see cref="CloseTimeout"/>.
/// </summary>
[ProviderAlias("OneNexus")]
public sealed class JsonLogProvider : ILoggerProvider, ISupportExternalScope
{
    public const int QueueCapacity = 1024;
    public static readonly TimeSpan CloseTimeout = TimeSpan.FromMilliseconds(2000);

    private readonly object gate = new();
    private readonly TextWriter writer;
    private readonly LogConfiguration configuration;
    private readonly Channel<string> queue = Channel.CreateBounded<string>(
        // Wait mode: TryWrite returns false when full, so every drop is counted (no silent Drop* mode).
        new BoundedChannelOptions(QueueCapacity) { SingleReader = true, FullMode = BoundedChannelFullMode.Wait });
    private readonly Task worker;
    private IExternalScopeProvider scopes = new LoggerExternalScopeProvider();
    private bool closed; // Guarded by gate.
    private long written, invalid, queueFull, ioErrors, closedDrops, pending;
    private readonly LogDropMetrics.ServiceDrops drops; // This service's process-wide drop metric (R1).
    private const string ErrorTypeField = "error.type";
    private const string StacktraceField = "exception.stacktrace";
    private const string TruncatedField = "logging.truncated";
    private const string DroppedField = "logging.dropped_field_count";
    private const string FingerprintField = "logging.error_fingerprint";
    private const string TruncationMark = "\u2026";
    private static readonly UTF8Encoding StrictUtf8 = new(false, true);

    /// <summary>Every line that was not written: invalid, queue full, write error, or logged after close.</summary>
    public long DroppedRecords => Interlocked.Read(ref invalid) + Interlocked.Read(ref queueFull) + Interlocked.Read(ref ioErrors) + Interlocked.Read(ref closedDrops);

    public LogWriteStats Stats => new(Interlocked.Read(ref written), Interlocked.Read(ref invalid), Interlocked.Read(ref queueFull),
        Interlocked.Read(ref ioErrors), Interlocked.Read(ref closedDrops), Interlocked.Read(ref pending));

    public JsonLogProvider(LogConfiguration configuration, TextWriter? writer = null)
    {
        this.configuration = configuration;
        this.writer = writer ?? Console.Out;
        drops = LogDropMetrics.Register(configuration.Service);
        // A dedicated background thread: a blocked output never holds a thread-pool thread or the process at exit.
        worker = Task.Factory.StartNew(Run, CancellationToken.None, TaskCreationOptions.LongRunning, TaskScheduler.Default);
    }

    public ILogger CreateLogger(string categoryName) => new Logger(this);
    public void SetScopeProvider(IExternalScopeProvider scopeProvider) => scopes = scopeProvider;

    /// <summary>Stop accepting lines and drain the queue for up to <see cref="CloseTimeout"/>. A second call is harmless.</summary>
    public void Dispose() => CloseWithin(CloseTimeout);

    /// <summary>
    /// Stop accepting lines (later ones are counted as closed) and wait up to <paramref name="timeout"/> for queued
    /// lines. True when nothing queued was lost; undelivered lines stay counted as pending. stdout and caller-owned
    /// writers are never closed by the provider.
    /// </summary>
    public bool CloseWithin(TimeSpan timeout)
    {
        lock (gate)
        {
            if (closed) return Interlocked.Read(ref pending) == 0;
            closed = true;
            queue.Writer.TryComplete();
        }
        try { worker.Wait(timeout); }
        catch (Exception) { } // The writer never faults; never throw into the caller.
        return Interlocked.Read(ref pending) == 0;
    }

    private void Submit(string line)
    {
        // The same gate as close: a close never sees a line that is counted pending but not yet queued.
        // Held only for a non-blocking TryWrite, never for the output.
        lock (gate)
        {
            if (closed)
            {
                Drop(ref closedDrops, DropReason.Closed);
                return;
            }
            Interlocked.Increment(ref pending);
            if (queue.Writer.TryWrite(line)) return;
            Interlocked.Decrement(ref pending);
            Drop(ref queueFull, DropReason.QueueFull);
        }
    }

    /// <summary>Count one line that was not written, on this provider and on its service's drop metric.</summary>
    private void Drop(ref long counter, DropReason reason)
    {
        Interlocked.Increment(ref counter);
        drops.Add(reason);
    }

    private void Run()
    {
        var reader = queue.Reader;
        // Blocks only this dedicated thread; ends once the channel is completed and empty.
        while (reader.WaitToReadAsync().AsTask().GetAwaiter().GetResult())
            while (reader.TryRead(out var line))
            {
                try
                {
                    writer.WriteLine(line);
                    Interlocked.Increment(ref written);
                }
                catch (Exception)
                {
                    // Never log a sink failure through this same logger; go on with the next line.
                    Drop(ref ioErrors, DropReason.IoErrors);
                }
                finally { Interlocked.Decrement(ref pending); }
            }
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
            // Before fitting: a shortened stack keeps the fingerprint.
            if (record.TryGetValue(ErrorTypeField, out var errorType) && errorType is string type)
                record[FingerprintField] = ErrorFingerprint(type, record.GetValueOrDefault(StacktraceField) as string);
            if (record.ContainsKey("event") != record.ContainsKey("outcome")) throw new ArgumentException("incomplete_event");
            var json = Fit(draft);
            var profile = record.ContainsKey("request_event") ? "request" : !record.ContainsKey("trace_id") ? "common" : record.ContainsKey("event") ? "lifecycle" : "correlated";
            if (Contract.Validate(json, profile).Count != 0) throw new ArgumentException("invalid_log_record");
            var line = json.GetRawText();
            if (Encoding.UTF8.GetByteCount(line) > Contract.MaxRecordBytes) throw new ArgumentException("record_too_large");
            Submit(line);
        }
        catch (Exception)
        {
            // Never log rejected data through this same logger.
            Drop(ref invalid, DropReason.Invalid);
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

    /// <summary>
    /// Groups one failure across lines and builds (tests/logging error_fingerprint): the type and each frame
    /// without its line number; never the message.
    /// </summary>
    public static string ErrorFingerprint(string errorType, string? stacktrace)
    {
        var text = new StringBuilder(errorType);
        if (!string.IsNullOrEmpty(stacktrace))
            foreach (var frame in stacktrace.Split('\n'))
                text.Append('\n').Append(WithoutLine(frame));
        return Convert.ToHexStringLower(SHA256.HashData(Encoding.UTF8.GetBytes(text.ToString())))[..16];
    }

    /// <summary>A trailing ':&lt;digits&gt;)' becomes ')'.</summary>
    private static string WithoutLine(string frame)
    {
        if (!frame.EndsWith(')')) return frame;
        var end = frame.Length - 1;
        var start = end;
        while (start > 0 && char.IsAsciiDigit(frame[start - 1])) start--;
        return start < end && start > 0 && frame[start - 1] == ':' ? frame[..(start - 1)] + ")" : frame;
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
