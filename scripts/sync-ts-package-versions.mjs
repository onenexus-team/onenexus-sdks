import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const repoRoot = dirname(dirname(fileURLToPath(import.meta.url)));
const version = readFileSync(join(repoRoot, 'VERSION'), 'utf8').trim();

if (!version) {
    throw new Error('VERSION must not be empty');
}

const packagePaths = [
    'ts/packages/sdk-core/package.json',
    'ts/packages/cas-client/package.json',
    'ts/packages/cas-support-client/package.json',
];

for (const packagePath of packagePaths) {
    const absolutePath = join(repoRoot, packagePath);
    const packageJson = JSON.parse(readFileSync(absolutePath, 'utf8'));

    packageJson.version = version;

    writeFileSync(absolutePath, `${JSON.stringify(packageJson, null, 4)}\n`);
    console.log(`${packageJson.name}@${version}`);
}