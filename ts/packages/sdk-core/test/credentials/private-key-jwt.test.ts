import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest';

import { AuthenticationError } from '../../src/credentials/credentials.js';
import { PrivateKeyJwtCredentials } from '../../src/credentials/private-key-jwt.js';
import { advanceServerClock, testContext } from '../helpers/context.js';
import { createMockOidcServer } from '../helpers/oidc-mock.js';

async function generateSigningKey(): Promise<CryptoKey> {
    const keyPair = await crypto.subtle.generateKey(
        {
            name: 'RSASSA-PKCS1-v1_5',
            modulusLength: 2048,
            publicExponent: new Uint8Array([1, 0, 1]),
            hash: 'SHA-256',
        },
        true,
        ['sign', 'verify'],
    );
    return keyPair.privateKey;
}

const mock = createMockOidcServer();
let signingKey: CryptoKey;

function decodeJwtPart(value: string): Record<string, unknown> {
    const decoded = Buffer.from(value, 'base64url').toString('utf-8');
    return JSON.parse(decoded) as Record<string, unknown>;
}

beforeAll(async () => {
    mock.server.listen({ onUnhandledRequest: 'error' });
    signingKey = await generateSigningKey();
});
afterEach(() => {
    mock.reset();
});
afterAll(() => {
    mock.server.close();
});

describe('PrivateKeyJwtCredentials', () => {
    it('resolve() performs a client_credentials grant with a private_key_jwt assertion', async () => {
        mock.queueTokenResponse({
            access_token: 'pkj-at-1',
            token_type: 'Bearer',
            expires_in: 3600,
            scope: 'mlops:read inference:invoke',
        });

        const context = testContext();
        const credentials = new PrivateKeyJwtCredentials({
            issuer: mock.issuer,
            clientId: 'acme-batch-recon',
            audience: 'mlops-api',
            scopes: ['mlops:read', 'inference:invoke'],
            signingKey,
            signingKeyId: 'acme-2026-q1',
        });

        const token = await credentials.resolve(context);

        expect(token.accessToken).toBe('pkj-at-1');
        expect(token.tokenType).toBe('Bearer');
        expect('scopes' in token).toBe(false);
        expect(token.expiresAt.getTime()).toBeGreaterThan(Date.now() + 3_500_000);

        expect(mock.tokenRequests).toHaveLength(1);
        const observed = mock.tokenRequests[0]!.form;
        expect(observed['grant_type']).toBe('client_credentials');
        expect(observed['audience']).toBe('mlops-api');
        expect(observed['scope']).toBe('mlops:read inference:invoke');
        expect(observed['client_id']).toBe('acme-batch-recon');
        expect(observed['client_assertion_type']).toBe(
            'urn:ietf:params:oauth:client-assertion-type:jwt-bearer',
        );
        expect(observed['client_assertion']).toBeTruthy();

        const [encodedHeader, encodedPayload] = observed['client_assertion']!.split('.');
        expect(encodedHeader).toBeDefined();
        expect(encodedPayload).toBeDefined();
        const header = decodeJwtPart(encodedHeader!);
        const payload = decodeJwtPart(encodedPayload!);
        expect(header['typ']).toBe('client-authentication+jwt');
        expect(header['kid']).toBe('acme-2026-q1');
        expect(payload['iss']).toBe('acme-batch-recon');
        expect(payload['sub']).toBe('acme-batch-recon');
        expect(payload['aud']).toBe(mock.issuer);
    });

    it('caches the access token across subsequent resolve() calls', async () => {
        mock.queueTokenResponse({ access_token: 'pkj-at-cached', expires_in: 3600 });

        const context = testContext();
        const credentials = new PrivateKeyJwtCredentials({
            issuer: mock.issuer,
            clientId: 'acme-batch-recon',
            signingKey,
            signingKeyId: 'kid',
        });

        const first = await credentials.resolve(context);
        const second = await credentials.resolve(context);
        const third = await credentials.resolve(context);

        expect(first.accessToken).toBe('pkj-at-cached');
        expect(second).toBe(first);
        expect(third).toBe(first);
        expect(mock.tokenRequests).toHaveLength(1);
    });

    it('single-flights concurrent first-call resolves into one token request', async () => {
        mock.queueTokenResponse({ access_token: 'pkj-at-single', expires_in: 3600 });

        const context = testContext();
        const credentials = new PrivateKeyJwtCredentials({
            issuer: mock.issuer,
            clientId: 'acme-batch-recon',
            signingKey,
            signingKeyId: 'kid',
        });

        const [a, b, c] = await Promise.all([
            credentials.resolve(context),
            credentials.resolve(context),
            credentials.resolve(context),
        ]);

        expect(a.accessToken).toBe('pkj-at-single');
        expect(b).toBe(a);
        expect(c).toBe(a);
        expect(mock.tokenRequests).toHaveLength(1);
    });

    it('performs a fresh grant when the cached token is stale by server clock', async () => {
        mock.queueTokenResponse({ access_token: 'pkj-at-first', expires_in: 3600 });
        mock.queueTokenResponse({ access_token: 'pkj-at-second', expires_in: 3600 });

        const context = testContext();
        const credentials = new PrivateKeyJwtCredentials({
            issuer: mock.issuer,
            clientId: 'acme-batch-recon',
            signingKey,
            signingKeyId: 'kid',
        });

        const first = await credentials.resolve(context);
        advanceServerClock(context, 3_700_000);
        const second = await credentials.resolve(context);

        expect(first.accessToken).toBe('pkj-at-first');
        expect(second.accessToken).toBe('pkj-at-second');
        expect(mock.tokenRequests).toHaveLength(2);
    });

    it('omits `scope` and `audience` from the request when not configured', async () => {
        mock.queueTokenResponse({ access_token: 'no-scope', expires_in: 3600 });

        const context = testContext();
        const credentials = new PrivateKeyJwtCredentials({
            issuer: mock.issuer,
            clientId: 'minimal',
            signingKey,
            signingKeyId: 'kid',
        });

        await credentials.resolve(context);
        const form = mock.tokenRequests[0]!.form;
        expect(form['scope']).toBeUndefined();
        expect(form['audience']).toBeUndefined();
    });

    it('maps token endpoint 401s to AuthenticationError', async () => {
        mock.queueTokenResponse({ error: 'invalid_client', status: 401 });

        const context = testContext();
        const credentials = new PrivateKeyJwtCredentials({
            issuer: mock.issuer,
            clientId: 'minimal',
            signingKey,
            signingKeyId: 'kid',
        });

        await expect(credentials.resolve(context)).rejects.toBeInstanceOf(AuthenticationError);
    });
});
