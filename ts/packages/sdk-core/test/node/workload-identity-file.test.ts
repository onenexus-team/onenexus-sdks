import { mkdtemp, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from 'vitest';

import { AuthenticationError } from '../../src/credentials/credentials.js';
import {
    WORKLOAD_IDENTITY_GRANT_TYPE,
    WORKLOAD_IDENTITY_SUBJECT_TOKEN_TYPE,
    WorkloadIdentityFileCredentials,
} from '../../src/node/workload-identity-file.js';
import { advanceServerClock, testContext } from '../helpers/context.js';
import { createMockOidcServer } from '../helpers/oidc-mock.js';

const mock = createMockOidcServer();

let tokenDir: string;
let tokenPath: string;

async function writeToken(content: string): Promise<void> {
    await writeFile(tokenPath, content, 'utf-8');
}

beforeAll(async () => {
    mock.server.listen({ onUnhandledRequest: 'error' });
    tokenDir = await mkdtemp(join(tmpdir(), 'workload-identity-test-'));
    tokenPath = join(tokenDir, 'token');
});
beforeEach(async () => {
    await writeToken('initial-workload-identity-token');
});
afterEach(() => {
    mock.reset();
});
afterAll(async () => {
    mock.server.close();
    await rm(tokenDir, { recursive: true, force: true });
});

describe('WorkloadIdentityFileCredentials', () => {
    it('resolve() reads the token from disk and presents it under the workload-identity grant', async () => {
        mock.queueTokenResponse({
            access_token: 'wif-at-1',
            expires_in: 3600,
            scope: 'inference:invoke',
        });

        const context = testContext();
        const credentials = new WorkloadIdentityFileCredentials({
            issuer: mock.issuer,
            clientId: 'notebook-runner',
            audience: 'inference-api',
            scopes: ['inference:invoke'],
            tokenPath,
        });

        const token = await credentials.resolve(context);
        expect(token.accessToken).toBe('wif-at-1');

        expect(mock.tokenRequests).toHaveLength(1);
        const form = mock.tokenRequests[0]!.form;
        expect(form['grant_type']).toBe(WORKLOAD_IDENTITY_GRANT_TYPE);
        expect(form['client_id']).toBe('notebook-runner');
        expect(form['subject_token']).toBe('initial-workload-identity-token');
        expect(form['subject_token_type']).toBe(WORKLOAD_IDENTITY_SUBJECT_TOKEN_TYPE);
        expect(form['audience']).toBe('inference-api');
        expect(form['scope']).toBe('inference:invoke');
    });

    it('omits client_id by default', async () => {
        mock.queueTokenResponse({ access_token: 'wif-at-default', expires_in: 3600 });

        const context = testContext();
        const credentials = new WorkloadIdentityFileCredentials({ issuer: mock.issuer, tokenPath });

        await credentials.resolve(context);
        expect(mock.tokenRequests[0]!.form['client_id']).toBeUndefined();
    });

    it('caches the CAS access token across resolve() calls', async () => {
        mock.queueTokenResponse({ access_token: 'wif-at-cached', expires_in: 3600 });

        const context = testContext();
        const credentials = new WorkloadIdentityFileCredentials({
            issuer: mock.issuer,
            clientId: 'notebook-runner',
            tokenPath,
        });

        const first = await credentials.resolve(context);
        const second = await credentials.resolve(context);
        expect(first).toBe(second);
        expect(mock.tokenRequests).toHaveLength(1);
    });

    it('re-reads the token from disk when the cached token is stale', async () => {
        mock.queueTokenResponse({ access_token: 'wif-at-1', expires_in: 3600 });
        mock.queueTokenResponse({ access_token: 'wif-at-2', expires_in: 3600 });

        const context = testContext();
        const credentials = new WorkloadIdentityFileCredentials({
            issuer: mock.issuer,
            clientId: 'notebook-runner',
            tokenPath,
        });

        await credentials.resolve(context);
        expect(mock.tokenRequests[0]!.form['subject_token']).toBe('initial-workload-identity-token');

        await writeToken('rotated-workload-identity-token');
        advanceServerClock(context, 3_700_000);

        await credentials.resolve(context);
        expect(mock.tokenRequests[1]!.form['subject_token']).toBe('rotated-workload-identity-token');
    });

    it('trims trailing whitespace/newlines from the file (common in projected tokens)', async () => {
        mock.queueTokenResponse({ access_token: 'wif-at-trim', expires_in: 3600 });
        await writeToken('token-with-trailing-newline\n');

        const context = testContext();
        const credentials = new WorkloadIdentityFileCredentials({
            issuer: mock.issuer,
            clientId: 'notebook-runner',
            tokenPath,
        });
        await credentials.resolve(context);
        expect(mock.tokenRequests[0]!.form['subject_token']).toBe('token-with-trailing-newline');
    });

    it('single-flights concurrent first-call resolves into one token request', async () => {
        mock.queueTokenResponse({ access_token: 'wif-at-single', expires_in: 3600 });

        const context = testContext();
        const credentials = new WorkloadIdentityFileCredentials({
            issuer: mock.issuer,
            clientId: 'notebook-runner',
            tokenPath,
        });

        const [a, b, c] = await Promise.all([
            credentials.resolve(context),
            credentials.resolve(context),
            credentials.resolve(context),
        ]);
        expect(a).toBe(b);
        expect(b).toBe(c);
        expect(mock.tokenRequests).toHaveLength(1);
    });

    it('propagates filesystem errors when the token path does not exist', async () => {
        const context = testContext();
        const credentials = new WorkloadIdentityFileCredentials({
            issuer: mock.issuer,
            clientId: 'notebook-runner',
            tokenPath: join(tokenDir, 'does-not-exist'),
        });
        await expect(credentials.resolve(context)).rejects.toThrow(/ENOENT/);
    });

    it('omits `scope` and `audience` when not configured', async () => {
        mock.queueTokenResponse({ access_token: 'wif-at-min', expires_in: 3600 });

        const context = testContext();
        const credentials = new WorkloadIdentityFileCredentials({
            issuer: mock.issuer,
            clientId: 'minimal-workload',
            tokenPath,
        });

        await credentials.resolve(context);
        const form = mock.tokenRequests[0]!.form;
        expect(form['audience']).toBeUndefined();
        expect(form['scope']).toBeUndefined();
    });

    it('maps token endpoint 401s to AuthenticationError', async () => {
        mock.queueTokenResponse({ error: 'invalid_client', status: 401 });

        const context = testContext();
        const credentials = new WorkloadIdentityFileCredentials({
            issuer: mock.issuer,
            clientId: 'minimal-workload',
            tokenPath,
        });

        await expect(credentials.resolve(context)).rejects.toBeInstanceOf(AuthenticationError);
    });
});
