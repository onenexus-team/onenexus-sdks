using Corvus.Json;

namespace OneNexus.Observability.Rules.Generated;

[JsonSchemaTypeGenerator("schema.json#/$defs/common")]
internal readonly partial struct CommonRecord;

[JsonSchemaTypeGenerator("schema.json#/$defs/correlated")]
internal readonly partial struct CorrelatedRecord;

[JsonSchemaTypeGenerator("schema.json#/$defs/lifecycle")]
internal readonly partial struct LifecycleRecord;

[JsonSchemaTypeGenerator("schema.json#/$defs/common/properties/message")]
internal readonly partial struct MessageValue;

[JsonSchemaTypeGenerator("schema.json#/$defs/common/properties/trace_id")]
internal readonly partial struct TraceValue;
