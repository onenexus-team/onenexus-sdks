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
    const loggingPath = join(repoRoot, 'ts/packages/observability/package.json');
    const logging = JSON.parse(readFileSync(loggingPath, 'utf8'));
    const lockPath = join(repoRoot, 'ts/pnpm-lock.yaml');
    const lock = readFileSync(lockPath, 'utf8');
    // Change only this known local link. Do not re-resolve external dependencies
    // or rely on registry metadata being cached on a clean release runner.
    const prefix = "  packages/observability:\n    dependencies:\n      '@onenexus-team/log-contract':\n        specifier: ";
    const suffix = '\n        version: link:../log-contract\n';
    const previous = prefix + logging.dependencies['@onenexus-team/log-contract'] + suffix;
    if (lock.split(previous).length !== 2)
        throw new Error('Expected exactly one observability contract workspace link in pnpm-lock.yaml');
    const updated = lock.replace(previous, prefix + `workspace:${contractVersion}` + suffix);
    contract.version = contractVersion;
    writeFileSync(contractPath, `${JSON.stringify(contract, null, 4)}\n`);
    logging.dependencies['@onenexus-team/log-contract'] = `workspace:${contractVersion}`;
    writeFileSync(loggingPath, `${JSON.stringify(logging, null, 4)}\n`);
    writeFileSync(lockPath, updated);
}
