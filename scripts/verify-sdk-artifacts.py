#!/usr/bin/env python3
"""Reject mismatched SDK versions or a reintroduced contract dependency before upload."""

import argparse
from email.parser import BytesParser
import json
from pathlib import Path
import re
import tarfile
import xml.etree.ElementTree as ET
import zipfile

EXPECTED = {
    "python": (
        "onenexus_sdk_core",
        "onenexus_cas_client",
        "onenexus_boto3",
        "onenexus_observability_python",
    ),
    "typescript": ("sdk-core", "cas-client", "cas-support-client", "observability"),
    "dotnet": ("OneNexus.Observability",),
    "go": ("observability",),
}


def verify(language, version, directory):
    if not re.fullmatch(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", version):
        raise ValueError("invalid_sdk_version")
    root = Path(directory)
    expected = {
        "python": {f"{n}-{version}-py3-none-any.whl" for n in EXPECTED["python"]},
        "typescript": {
            f"onenexus-team-{n}-{version}.tgz" for n in EXPECTED["typescript"]
        },
        "dotnet": {f"OneNexus.Observability.{version}.nupkg"},
        "go": {f"observability-go-v{version}.zip"},
    }[language]
    if {p.name for p in root.iterdir()} != expected:
        raise ValueError("unexpected_sdk_artifact_inventory")
    for name in expected:
        path = root / name
        if language == "python":
            with zipfile.ZipFile(path) as z:
                (metadata,) = [
                    n for n in z.namelist() if n.endswith(".dist-info/METADATA")
                ]
                m = BytesParser().parsebytes(z.read(metadata))
                if (
                    m["Version"] != version
                    or m["Name"].replace("-", "_") not in EXPECTED["python"]
                ):
                    raise ValueError("python_sdk_version_or_name_mismatch")
                if any(
                    "log-contract" in x.lower() or "log_contract" in x.lower()
                    for x in m.get_all("Requires-Dist", [])
                ):
                    raise ValueError("separate_contract_dependency")
                if (
                    "observability_python" in name
                    and "onenexus_observability/schema.json" not in z.namelist()
                ):
                    raise ValueError("missing_embedded_rules")
        elif language == "typescript":
            with tarfile.open(path) as t:
                m = json.load(t.extractfile("package/package.json"))
            if m["version"] != version or m[
                "name"
            ] != "@onenexus-team/" + name.removeprefix("onenexus-team-").removesuffix(
                f"-{version}.tgz"
            ):
                raise ValueError("npm_sdk_version_or_name_mismatch")
            if any("log-contract" in n for n in m.get("dependencies", {})):
                raise ValueError("separate_contract_dependency")
        elif language == "dotnet":
            with zipfile.ZipFile(path) as z:
                (nuspec,) = [n for n in z.namelist() if n.endswith(".nuspec")]
                m = ET.fromstring(z.read(nuspec))
            if (
                m.findtext(".//{*}version") != version
                or m.findtext(".//{*}id") != "OneNexus.Observability"
            ):
                raise ValueError("nuget_sdk_version_or_name_mismatch")
            if any(
                "logcontract" in n.attrib.get("id", "").lower()
                for n in m.findall(".//{*}dependency")
            ):
                raise ValueError("separate_contract_dependency")
        else:
            prefix = (
                f"github.com/onenexus-team/onenexus-sdks/go/observability@v{version}/"
            )
            with zipfile.ZipFile(path) as z:
                if any(not n.startswith(prefix) for n in z.namelist()):
                    raise ValueError("go_sdk_version_mismatch")
                mod = z.read(prefix + "go.mod").decode()
                if "contracts/log-correlation" in mod or "\nreplace " in mod:
                    raise ValueError("separate_contract_dependency")
                z.read(prefix + "schema.json")
    return len(expected)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("language", choices=EXPECTED)
    p.add_argument("version")
    p.add_argument("directory", type=Path)
    args = p.parse_args()
    print(
        f"PASS: {verify(args.language, args.version, args.directory)} {args.language} SDK artifacts at {args.version}"
    )
