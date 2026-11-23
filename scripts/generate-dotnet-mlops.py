"""Prepare the FastAPI schema for Kiota and emit the typed MLOps facade."""

import json
from pathlib import Path
import re
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "dotnet/src/OneNexus.Sdk.MLOps"
SPEC = ROOT / "specs/mlops/openapi.json"

# These four service handlers authenticate a platform API key in the bearer header.
KEY_ROUTES = {
    "/v1/models",
    "/api/v1/composer-configs",
    "/api/v1/WebTools/Search",
    "/api/v1/WebTools/Fetch",
}
# The service deliberately bypasses command replay for metered retrieval and inference.
ONCE = {
    "/api/v1/WebTools/Search",
    "/api/v1/WebTools/Fetch",
    "/api/v1/Inference/InvokeInferencePublicEndpoint",
}
GET_NAMES = {
    "/v1/models": "ListOpenAIModels",
    "/api/v1/composer-configs": "GetComposerConfigs",
    "/api/v1/health": "GetHealth",
}


def normalize(value):
    if isinstance(value, list):
        return [normalize(item) for item in value]
    if not isinstance(value, dict):
        return value
    schema = {key: normalize(item) for key, item in value.items()}
    variants = schema.get("anyOf", [])
    if len(variants) == 2 and {"type": "null"} in variants:
        inner = next(item for item in variants if item != {"type": "null"})
        # The two alternatives are disjoint. Prefer the native nullable type
        # over a generated wrapper with an empty model for the JSON null arm.
        if "type" in inner:
            del schema["anyOf"]
            schema.update(inner, type=[inner["type"], "null"])
            # Kiota emits Nullable<TEnum> for this type. A null enum member
            # would also create a fictitious string value on the wire.
            if "const" in inner:
                schema["enum"] = [schema.pop("const")]
        elif "$ref" in inner:
            schema["oneOf"] = schema.pop("anyOf")
        elif "oneOf" in inner and "discriminator" in inner:
            del schema["anyOf"]
            # The reference property is nullable in C#. Keep its discriminated
            # alternatives directly visible to the generator.
            schema.update(inner)
    return schema


def model(schema):
    return schema["$ref"].rsplit("/", 1)[1]


def operation(path, verb, op, schemas):
    name = GET_NAMES.get(path, path.rsplit("/", 1)[1])
    builder = ".".join(
        part[0].upper() + part[1:]
        for part in path.strip("/")
        .replace("composer-configs", "ComposerConfigs")
        .split("/")
    )
    params, args = [], []
    if "requestBody" in op:
        request = model(op["requestBody"]["content"]["application/json"]["schema"])
        if not schemas[request].get("required") and path not in KEY_ROUTES:
            params.append(f"{request}? request = null")
            args.append(f"request ?? new {request}()")
        else:
            params.append(f"{request} request")
            args.append("request")
    key_auth = path in KEY_ROUTES
    anonymous = path in {"/api/v1/Inference/ValidateInferenceKey", "/api/v1/health"}
    keyed = (
        verb == "post"
        and not re.match(r"^(Get|List|Resolve|Validate)[A-Z]", name)
        and path not in ONCE
        and path not in KEY_ROUTES
    )
    if key_auth:
        params.append("string platformApiKey")
        args.append(
            "config => UsePlatformKey(config, platformApiKey, retry: "
            + ("false" if path in ONCE else "true")
            + ")"
        )
    elif anonymous:
        args.append("UseAnonymous")
    elif path in ONCE:
        args.append("DisableRetries")
    elif keyed:
        args.append("config => AddIdempotencyKey(config, idempotencyKey)")
    default_params = [*params, "CancellationToken cancellationToken = default"]
    if keyed:
        params = [p.removesuffix(" = null") for p in params]
        params.append("string? idempotencyKey")
    params.append("CancellationToken cancellationToken = default")
    args.append("cancellationToken: cancellationToken")
    responses = {
        code: resp for code, resp in op["responses"].items() if code.startswith("2")
    }
    bodies = [
        resp["content"]["application/json"]["schema"]
        for resp in responses.values()
        if resp.get("content")
    ]
    if len({json.dumps(body, sort_keys=True) for body in bodies}) > 1:
        raise ValueError(f"Multiple successful response types for {path}")
    typ = (model(bodies[0]) if bodies[0] else "UntypedNode") if bodies else None
    nullable = typ and "204" in responses
    result = f"Task<{typ}{'?' if nullable else ''}>" if typ else "Task"
    method = name + "Async"
    summary = (
        f"    /// <summary>{escape(op['summary'])} ({verb.upper()} {path}).</summary>"
    )
    call = f"_api.{builder}.{verb.title()}Async(\n            {', '.join(args)})"
    if typ and not nullable:
        indented = call.replace("\n", "\n    ")
        call = f"ServiceTransport.RequiredAsync(\n            {indented})"

    def signature(parameters):
        line = f"    public {result} {method}("
        joined = ", ".join(parameters)
        if len(line) + len(joined) > 140:
            joined = "\n        " + ",\n        ".join(parameters)
        return line + joined + ") =>"

    lines = []
    if keyed:
        lines += [
            summary,
            signature(default_params),
            f"        {method}(request, idempotencyKey: null, cancellationToken);",
            "",
        ]
    lines.append(summary)
    if keyed:
        lines.append(
            "    /// <remarks>Supply the same key and request body to replay a timed-out operation.</remarks>"
        )
    lines += [signature(params), f"        {call};"]
    return "\n".join(lines) + "\n"


def main():
    spec = json.loads(SPEC.read_bytes())
    schema = normalize(spec)
    # FastAPI's export contains JSON Schema 2020-12 numeric exclusive bounds.
    schema["openapi"] = "3.1.0"
    target = PROJECT / "obj/kiota/openapi.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(schema), encoding="utf-8")
    methods = [
        operation(path, verb, op, spec["components"]["schemas"])
        for path, item in sorted(spec["paths"].items())
        for verb, op in item.items()
    ]
    (PROJECT / "MLOpsClient.Operations.g.cs").write_text(
        """// <auto-generated by scripts/generate-dotnet-mlops.py />
#nullable enable
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Kiota.Abstractions.Serialization;
using OneNexus.Sdk.Core;
using OneNexus.Sdk.MLOps.Models;

namespace OneNexus.Sdk.MLOps;

public sealed partial class MLOpsClient
{
"""
        + "\n".join(methods)
        + "}\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
