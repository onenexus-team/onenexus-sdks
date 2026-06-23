import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest';

import type { AccessToken } from '../../src/credentials/credentials.js';
import { AuthenticationError, StaleCredentialsError } from '../../src/credentials/credentials.js';
import { TokenGrantCredentials } from '../../src/credentials/token-credentials.js';
import { advanceServerClock, testContext } from '../helpers/context.js';
import { createMockOidcServer } from '../helpers/oidc-mock.js';

const mock = createMockOidcServer();

const fixtureToken: AccessToken = {
    accessToken: 'access-abc',
    tokenType: 'Bearer',
    expiresAt: new Date('2030-01-01T00:00:00Z'),
};

beforeAll(() => {
    mock.server.listen({ onUnhandledRequest: 'error' });
});
afterEach(() => {
    mock.reset();
});
afterAll(() => {
    mock.server.close();
});

describe('TokenGrantCredentials', () => {
    it('resolve() returns the held access token while it is live', async () => {
        const context = testContext();
        const credentials = new TokenGrantCredentials({ token: fixtureToken });

        await expect(credentials.resolve(context)).resolves.toBe(fixtureToken);
    });

    it('keeps grant metadata outside the AccessToken value', async () => {
        const context = testContext();
        const credentials = new TokenGrantCredentials({
            token: fixtureToken,
            idToken: 'id-token',
            scopes: ['platform:read'],
        });

        const token = await credentials.resolve(context);

        expect(token).toEqual(fixtureToken);
        expect('scopes' in token).toBe(false);
        expect('idToken' in token).toBe(false);
        expect(credentials.idToken).toBe('id-token');
        expect(credentials.scopes).toEqual(['platform:read']);
    });

    it('throws StaleCredentialsError when stale and no refresh grant is configured', async () => {
        const context = testContext();
        const credentials = new TokenGrantCredentials({
            token: { ...fixtureToken, expiresAt: new Date('2000-01-01T00:00:00Z') },
        });

        await expect(credentials.resolve(context)).rejects.toBeInstanceOf(StaleCredentialsError);
    });

    it('uses the client context refresh leeway by default', async () => {
        const context = { ...testContext(), refreshLeewayMs: 120_000 };
        const credentials = new TokenGrantCredentials({
            token: { ...fixtureToken, expiresAt: new Date(Date.now() + 60_000) },
        });

        await expect(credentials.resolve(context)).rejects.toBeInstanceOf(StaleCredentialsError);
    });

    it('lets credential refreshLeewayMs override the client context leeway', async () => {
        const context = { ...testContext(), refreshLeewayMs: 120_000 };
        const token = { ...fixtureToken, expiresAt: new Date(Date.now() + 60_000) };
        const credentials = new TokenGrantCredentials({ token, refreshLeewayMs: 10_000 });

        await expect(credentials.resolve(context)).resolves.toBe(token);
    });

    it('refreshes using refresh_token when the access token is stale', async () => {
        mock.queueTokenResponse({
            access_token: 'refreshed-at',
            refresh_token: 'rotated-rt',
            expires_in: 3600,
            scope: 'platform:read inference:invoke',
        });

        const context = testContext();
        const credentials = new TokenGrantCredentials({
            token: { ...fixtureToken, expiresAt: new Date(Date.now() + 1_000) },
            refreshToken: 'initial-rt',
            issuer: mock.issuer,
            clientId: 'onenexus-portal',
        });

        const token = await credentials.resolve(context);

        expect(token.accessToken).toBe('refreshed-at');
        expect(credentials.scopes).toEqual(['platform:read', 'inference:invoke']);
        expect(credentials.snapshot().refreshToken).toBe('rotated-rt');

        expect(mock.tokenRequests).toHaveLength(1);
        const form = mock.tokenRequests[0]!.form;
        expect(form['grant_type']).toBe('refresh_token');
        expect(form['refresh_token']).toBe('initial-rt');
        expect(form['client_id']).toBe('onenexus-portal');
    });

    it('single-flights concurrent refresh calls into one token request', async () => {
        mock.queueTokenResponse({ access_token: 'single-flight-at', expires_in: 3600 });

        const context = testContext();
        const credentials = new TokenGrantCredentials({
            token: { ...fixtureToken, expiresAt: new Date(Date.now() + 1_000) },
            refreshToken: 'rt',
            issuer: mock.issuer,
            clientId: 'onenexus-portal',
        });

        const [a, b, c] = await Promise.all([
            credentials.resolve(context),
            credentials.resolve(context),
            credentials.resolve(context),
        ]);

        expect(a.accessToken).toBe('single-flight-at');
        expect(b).toBe(a);
        expect(c).toBe(a);
        expect(mock.tokenRequests).toHaveLength(1);
    });

    it('refreshes again after the server clock moves past the cached expiry', async () => {
        mock.queueTokenResponse({ access_token: 'first-at', refresh_token: 'rt-2', expires_in: 3600 });
        mock.queueTokenResponse({ access_token: 'second-at', refresh_token: 'rt-3', expires_in: 3600 });

        const context = testContext();
        const credentials = new TokenGrantCredentials({
            token: { ...fixtureToken, expiresAt: new Date(Date.now() + 1_000) },
            refreshToken: 'rt-1',
            issuer: mock.issuer,
            clientId: 'onenexus-portal',
        });

        const first = await credentials.resolve(context);
        advanceServerClock(context, 3_700_000);
        const second = await credentials.resolve(context);

        expect(first.accessToken).toBe('first-at');
        expect(second.accessToken).toBe('second-at');
        expect(mock.tokenRequests[1]!.form['refresh_token']).toBe('rt-2');
    });

    it('maps refresh-token 401s to AuthenticationError', async () => {
        mock.queueTokenResponse({ error: 'invalid_grant', status: 401 });

        const context = testContext();
        const credentials = new TokenGrantCredentials({
            token: { ...fixtureToken, expiresAt: new Date(Date.now() + 1_000) },
            refreshToken: 'revoked-rt',
            issuer: mock.issuer,
            clientId: 'onenexus-portal',
        });

        await expect(credentials.resolve(context)).rejects.toBeInstanceOf(AuthenticationError);
    });
});
