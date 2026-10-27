using Corvus.Json;

namespace OneNexus.LogContract.Generated;

[JsonSchemaTypeGenerator("../../../contracts/log-correlation/schema.json#/$defs/common")]
internal readonly partial struct CommonRecord;

[JsonSchemaTypeGenerator("../../../contracts/log-correlation/schema.json#/$defs/correlated")]
internal readonly partial struct CorrelatedRecord;

[JsonSchemaTypeGenerator("../../../contracts/log-correlation/schema.json#/$defs/lifecycle")]
internal readonly partial struct LifecycleRecord;

[JsonSchemaTypeGenerator("../../../contracts/log-correlation/schema.json#/$defs/common/properties/message")]
internal readonly partial struct MessageValue;

[JsonSchemaTypeGenerator("../../../contracts/log-correlation/schema.json#/$defs/common/properties/trace_id")]
internal readonly partial struct TraceValue;
