import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from 'vitest';

import type { AccessToken, ClientContext, Credentials } from '../../src/credentials/credentials.js';
import { AuthenticationError, StaleCredentialsError } from '../../src/credentials/credentials.js';
import { createKy } from '../../src/http/ky-client.js';
import { testContext } from '../helpers/context.js';

const BASE_URL = 'https://cas.test.invalid';

function token(label: string): AccessToken {
    return {
        accessToken: `at-${label}`,
        tokenType: 'Bearer',
        expiresAt: new Date('2030-01-01T00:00:00Z'),
    };
}

function makeCredentials(accessToken: AccessToken): Credentials & {
    resolveSpy: ReturnType<typeof vi.fn>;
} {
    const resolveSpy = vi.fn().mockResolvedValue(accessToken);
    return {
        resolve: resolveSpy,
        resolveSpy,
    };
}

const server = setupServer();

beforeAll(() => {
    server.listen({ onUnhandledRequest: 'error' });
});
afterEach(() => {
    server.resetHandlers();
    vi.restoreAllMocks();
});
afterAll(() => {
    server.close();
});

describe('createKy', () => {
    it('sets the Authorization header from credentials on each request', async () => {
        const context = testContext();
        const credentials = makeCredentials(token('initial'));
        const observed: string[] = [];

        server.use(
            http.post(`${BASE_URL}/api/Ping`, ({ request }) => {
                observed.push(request.headers.get('authorization') ?? '');
                return HttpResponse.json({ ok: true });
            }),
        );

        const kyInstance = createKy({ baseUrl: BASE_URL, credentials, context });

        await kyInstance.post('api/Ping').json();
        await kyInstance.post('api/Ping').json();

        expect(observed).toEqual(['Bearer at-initial', 'Bearer at-initial']);
        expect(credentials.resolveSpy).toHaveBeenCalledTimes(2);
        expect(credentials.resolveSpy).toHaveBeenCalledWith(context, expect.any(AbortSignal));
    });

    it('records the server Date header into the client context clock', async () => {
        const context = testContext();
        const credentials = makeCredentials(token('initial'));
        const serverDate = new Date(Date.now() + 120_000);

        server.use(
            http.post(`${BASE_URL}/api/Ping`, () =>
                HttpResponse.json(
                    { ok: true },
                    { headers: { date: serverDate.toUTCString() } },
                ),
            ),
        );

        const kyInstance = createKy({ baseUrl: BASE_URL, credentials, context });
        await kyInstance.post('api/Ping').json();

        expect(context.clock.serverNow()).toBeGreaterThan(Date.now() + 110_000);
    });

    it('on 401, records server time and retries; next resolve can use the updated clock', async () => {
        const context = testContext();
        const stale = token('stale');
        const fresh = token('fresh');
        const cutoff = Date.now() + 60_000;
        const resolveSpy = vi.fn((resolveContext: ClientContext) =>
            Promise.resolve(resolveContext.clock.serverNow() >= cutoff ? fresh : stale),
        );
        const credentials: Credentials = { resolve: resolveSpy };

        const observedAuth: string[] = [];
        let callCount = 0;

        server.use(
            http.post(`${BASE_URL}/api/Op`, ({ request }) => {
                observedAuth.push(request.headers.get('authorization') ?? '');
                callCount += 1;
                if (callCount === 1) {
                    return HttpResponse.json(
                        { code: 'unauthenticated', detail: 'token expired' },
                        {
                            status: 401,
                            headers: {
                                'content-type': 'application/problem+json',
                                date: new Date(cutoff + 1_000).toUTCString(),
                            },
                        },
                    );
                }
                return HttpResponse.json({ ok: true });
            }),
        );

        const kyInstance = createKy({ baseUrl: BASE_URL, credentials, context });
        const result = await kyInstance.post('api/Op').json<{ ok: boolean }>();

        expect(result).toEqual({ ok: true });
        expect(observedAuth).toEqual(['Bearer at-stale', 'Bearer at-fresh']);
        expect(resolveSpy).toHaveBeenCalledTimes(2);
    });

    it('does not mutate credential state on retry-able non-auth statuses', async () => {
        const context = testContext();
        const credentials = makeCredentials(token('ok'));
        let callCount = 0;

        server.use(
            http.post(`${BASE_URL}/api/Op`, () => {
                callCount += 1;
                if (callCount === 1) {
                    return HttpResponse.json(
                        { code: 'unavailable', detail: 'db down' },
                        { status: 503, headers: { 'content-type': 'application/problem+json' } },
                    );
                }
                return HttpResponse.json({ ok: true });
            }),
        );

        const kyInstance = createKy({ baseUrl: BASE_URL, credentials, context });
        await kyInstance.post('api/Op').json();

        expect(credentials.resolveSpy).toHaveBeenCalledTimes(2);
    });

    it('honours retry.limit', async () => {
        const context = testContext();
        const credentials = makeCredentials(token('x'));
        let callCount = 0;

        server.use(
            http.post(`${BASE_URL}/api/Op`, () => {
                callCount += 1;
                return HttpResponse.json(
                    { code: 'unavailable', detail: 'down' },
                    { status: 503, headers: { 'content-type': 'application/problem+json' } },
                );
            }),
        );

        const kyInstance = createKy({
            baseUrl: BASE_URL,
            credentials,
            context,
            retry: { limit: 1 },
        });

        await expect(kyInstance.post('api/Op')).rejects.toBeDefined();
        expect(callCount).toBe(2);
    });

    it('uses full-jitter exponential retry delay capped by retry.backoffLimitMs', async () => {
        const context = testContext();
        const credentials = makeCredentials(token('x'));
        const setTimeoutSpy = vi.spyOn(globalThis, 'setTimeout');
        vi.spyOn(Math, 'random').mockReturnValue(1);

        server.use(
            http.post(`${BASE_URL}/api/Op`, () =>
                HttpResponse.json(
                    { code: 'unavailable', detail: 'down' },
                    { status: 503, headers: { 'content-type': 'application/problem+json' } },
                ),
            ),
        );

        const kyInstance = createKy({
            baseUrl: BASE_URL,
            credentials,
            context,
            retry: { limit: 2, backoffLimitMs: 400 },
        });

        await expect(kyInstance.post('api/Op')).rejects.toBeDefined();

        const retryDelays = setTimeoutSpy.mock.calls
            .map((call) => call[1])
            .filter((delay): delay is number => typeof delay === 'number');
        expect(retryDelays).toContain(300);
        expect(retryDelays).toContain(400);
    });

    it('fails fast when credentials throw StaleCredentialsError', async () => {
        const context = testContext();
        const resolveSpy = vi.fn().mockRejectedValue(new StaleCredentialsError('stale'));
        const credentials: Credentials = { resolve: resolveSpy };
        const kyInstance = createKy({ baseUrl: BASE_URL, credentials, context });

        await expect(kyInstance.post('api/Op')).rejects.toBeInstanceOf(StaleCredentialsError);
        expect(resolveSpy).toHaveBeenCalledOnce();
    });

    it('fails fast when credentials throw AuthenticationError', async () => {
        const context = testContext();
        const resolveSpy = vi.fn().mockRejectedValue(new AuthenticationError('auth failed'));
        const credentials: Credentials = { resolve: resolveSpy };
        const kyInstance = createKy({ baseUrl: BASE_URL, credentials, context });

        await expect(kyInstance.post('api/Op')).rejects.toBeInstanceOf(AuthenticationError);
        expect(resolveSpy).toHaveBeenCalledOnce();
    });
});
