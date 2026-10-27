import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const repoRoot = dirname(dirname(fileURLToPath(import.meta.url)));
const version = process.env.SDK_PACKAGE_VERSION ?? readFileSync(join(repoRoot, 'VERSION'), 'utf8').trim();

if (!version) {
    throw new Error('VERSION must not be empty');
}

const packagePaths = [
    'ts/packages/observability/package.json',
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

// Contract tags own this version. Ordinary SDK releases preserve the reviewed pin.
if (process.env.LOG_CONTRACT_PACKAGE_VERSION) {
    const contractVersion = process.env.LOG_CONTRACT_PACKAGE_VERSION;
    if (!/^\d+\.\d+\.\d+(-[a-z0-9]+(\.[a-z0-9]+)*)?$/.test(contractVersion))
        throw new Error('Invalid contract package version');
    const contractPath = join(repoRoot, 'ts/packages/log-contract/package.json');
    const contract = JSON.parse(readFileSync(contractPath, 'utf8'));
    contract.version = contractVersion;
    writeFileSync(contractPath, `${JSON.stringify(contract, null, 4)}\n`);
    const loggingPath = join(repoRoot, 'ts/packages/observability/package.json');
    const logging = JSON.parse(readFileSync(loggingPath, 'utf8'));
    logging.dependencies['@onenexus-team/log-contract'] = `workspace:${contractVersion}`;
    writeFileSync(loggingPath, `${JSON.stringify(logging, null, 4)}\n`);
}
