// Build-time input only. Published packages never fetch schemas at runtime.
import { createHash } from "node:crypto";
import { readFileSync, mkdirSync, writeFileSync } from "node:fs";
const root = new URL("../", import.meta.url);
const source = new URL("contracts/log-correlation/", root);
const manifestText = readFileSync(new URL("manifest.json", source), "utf8");
const manifest = JSON.parse(manifestText);
const hash = createHash("sha256");
const files = {};
for (const { path, sha256 } of manifest.files) {
  if (!["schema.json", "vectors.json"].includes(path))
    throw Error("unexpected_contract_file");
  const bytes = readFileSync(new URL(path, source));
  if (createHash("sha256").update(bytes).digest("hex") !== sha256)
    throw Error("contract_hash_mismatch");
  hash.update(path + "\0").update(bytes);
  files[path] = bytes.toString("utf8");
}
if (hash.digest("hex") !== manifest.sha256)
  throw Error("contract_digest_mismatch");
if (
  JSON.parse(files["schema.json"])["x-contract-version"] !== manifest.version ||
  JSON.parse(files["vectors.json"]).contract_version !== manifest.version
)
  throw Error("contract_version_mismatch");
const output = new URL("ts/packages/log-contract/src/generated/", root);
mkdirSync(output, { recursive: true });
writeFileSync(
  new URL("data.ts", output),
  "// Generated from contracts/log-correlation. Do not edit.\n" +
    Object.entries({
      manifestText,
      schemaText: files["schema.json"],
      vectorsText: files["vectors.json"],
    })
      .map(([key, value]) => `export const ${key} = ${JSON.stringify(value)};`)
      .join("\n") +
    "\n",
);
console.log(
  `Generated TypeScript contract ${manifest.version} (${manifest.sha256})`,
);
