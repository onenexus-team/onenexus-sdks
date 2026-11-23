using System.Text.Json;
using System.Text.Json.Serialization;

namespace OneNexus.Sdk.Core;

[JsonSourceGenerationOptions(JsonSerializerDefaults.Web, GenerationMode = JsonSourceGenerationMode.Metadata)]
[JsonSerializable(typeof(JsonDocument))]
[JsonSerializable(typeof(JsonElement))]
[JsonSerializable(typeof(PlatformException.Problem))]
internal sealed partial class SdkJsonContext : JsonSerializerContext;
