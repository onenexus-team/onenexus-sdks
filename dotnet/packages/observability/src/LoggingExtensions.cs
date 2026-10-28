using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;

namespace OneNexus.Observability;

public static class LoggingExtensions
{
    private sealed record Registration(LogConfiguration Configuration, TextWriter Writer);

    /// <summary>Register once at startup. Does not remove other providers or change log levels.</summary>
    public static ILoggingBuilder AddOneNexus(this ILoggingBuilder builder, LogConfiguration configuration, TextWriter? writer = null)
    {
        writer ??= Console.Out;
        var existing = builder.Services.FirstOrDefault(d => d.ServiceType == typeof(Registration))?.ImplementationInstance as Registration;
        if (existing is not null)
        {
            if (!existing.Configuration.Equivalent(configuration) || !ReferenceEquals(existing.Writer, writer))
                throw new InvalidOperationException("logging_configuration_conflict");
            return builder;
        }
        builder.Services.AddSingleton(new Registration(configuration, writer));
        builder.Services.AddSingleton<JsonLogProvider>(_ => new JsonLogProvider(configuration, writer));
        builder.Services.AddSingleton<ILoggerProvider>(services => services.GetRequiredService<JsonLogProvider>());
        return builder;
    }
}
