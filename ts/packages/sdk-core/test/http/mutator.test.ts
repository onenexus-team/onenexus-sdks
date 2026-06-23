import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest';

import type { Credentials } from '../../src/credentials/credentials.js';
import { TokenGrantCredentials } from '../../src/credentials/token-credentials.js';
import { AlreadyExistsError, InvalidArgumentError } from '../../src/http/errors.js';
import { createKy } from '../../src/http/ky-client.js';
import { platformMutator } from '../../src/http/mutator.js';
import { testContext } from '../helpers/context.js';

const BASE_URL = 'https://cas.test.invalid';

function staticCreds(): Credentials {
    return new TokenGrantCredentials({
        token: {
            accessToken: 'static-at',
            tokenType: 'Bearer',
            expiresAt: new Date('2030-01-01T00:00:00Z'),
        },
    });
}

function testKy() {
    return createKy({ baseUrl: BASE_URL, credentials: staticCreds(), context: testContext() });
}

const server = setupServer();
beforeAll(() => {
    server.listen({ onUnhandledRequest: 'error' });
});
afterEach(() => {
    server.resetHandlers();
});
afterAll(() => {
    server.close();
});

describe('platformMutator', () => {
    it('throws synchronously when options.http is missing', async () => {
        await expect(platformMutator({ url: 'api/Op', method: 'POST' })).rejects.toThrowError(
            /requires options\.http/,
        );
    });

    it('issues a POST with body, headers, and parsed JSON response', async () => {
        let observed: { method: string; body: unknown; auth: string | null } | undefined;

        server.use(
            http.post(`${BASE_URL}/api/CreateUser`, async ({ request }) => {
                observed = {
                    method: request.method,
                    body: await request.json(),
                    auth: request.headers.get('authorization'),
                };
                return HttpResponse.json({ userId: 'u-1' });
            }),
        );

        const kyInstance = testKy();
        const result = await platformMutator<{ userId: string }>(
            {
                url: 'api/CreateUser',
                method: 'POST',
                data: { tenantId: 'tn_acme', email: 'a@b.c' },
                headers: { 'content-type': 'application/json' },
            },
            { http: kyInstance },
        );

        expect(result).toEqual({ userId: 'u-1' });
        expect(observed?.method).toBe('POST');
        expect(observed?.body).toEqual({ tenantId: 'tn_acme', email: 'a@b.c' });
        expect(observed?.auth).toBe('Bearer static-at');
    });

    it('strips a leading slash from the URL (Ky prefixUrl requires relative)', async () => {
        let observedPath: string | undefined;
        server.use(
            http.post(`${BASE_URL}/api/Op`, ({ request }) => {
                observedPath = new URL(request.url).pathname;
                return HttpResponse.json({ ok: true });
            }),
        );

        const kyInstance = testKy();
        await platformMutator({ url: '/api/Op', method: 'POST' }, { http: kyInstance });
        expect(observedPath).toBe('/api/Op');
    });

    it('serialises params into the query string', async () => {
        let observedSearch: string | undefined;
        server.use(
            http.get(`${BASE_URL}/api/List`, ({ request }) => {
                observedSearch = new URL(request.url).search;
                return HttpResponse.json({ items: [] });
            }),
        );

        const kyInstance = testKy();
        await platformMutator(
            {
                url: 'api/List',
                method: 'GET',
                params: { pageSize: 10, tags: ['a', 'b'], skip: undefined },
            },
            { http: kyInstance },
        );
        expect(observedSearch).toBe('?pageSize=10&tags=a&tags=b');
    });

    it('returns undefined for 204 No Content', async () => {
        server.use(http.post(`${BASE_URL}/api/Op`, () => new HttpResponse(null, { status: 204 })));
        const kyInstance = testKy();
        const result = await platformMutator(
            { url: 'api/Op', method: 'POST' },
            { http: kyInstance },
        );
        expect(result).toBeUndefined();
    });

    it('translates HTTPError(409) with already_exists code → AlreadyExistsError', async () => {
        server.use(
            http.post(`${BASE_URL}/api/CreateTenant`, () =>
                HttpResponse.json(
                    {
                        type: 'https://docs.onenexus.vn/errors/already-exists',
                        title: 'Tenant already exists',
                        status: 409,
                        detail: "Tenant 'tn_acme' already exists.",
                        instance: '/api/CreateTenant',
                        code: 'already_exists',
                        requestId: 'trace-1',
                    },
                    { status: 409, headers: { 'content-type': 'application/problem+json' } },
                ),
            ),
        );

        const kyInstance = createKy({
            baseUrl: BASE_URL,
            credentials: staticCreds(),
            context: testContext(),
            retry: { limit: 0 },
        });

        const promise = platformMutator(
            { url: 'api/CreateTenant', method: 'POST', data: { tenantId: 'tn_acme' } },
            { http: kyInstance },
        );

        await expect(promise).rejects.toBeInstanceOf(AlreadyExistsError);
        await promise.catch((error: unknown) => {
            const e = error as AlreadyExistsError;
            expect(e.code).toBe('already_exists');
            expect(e.requestId).toBe('trace-1');
            expect(e.detail).toBe("Tenant 'tn_acme' already exists.");
        });
    });

    it('translates HTTPError(400) with field errors → InvalidArgumentError', async () => {
        server.use(
            http.post(`${BASE_URL}/api/CreateTenant`, () =>
                HttpResponse.json(
                    {
                        code: 'invalid_argument',
                        status: 400,
                        detail: 'See errors',
                        errors: { tenantId: ['Required'] },
                    },
                    { status: 400, headers: { 'content-type': 'application/problem+json' } },
                ),
            ),
        );

        const kyInstance = createKy({
            baseUrl: BASE_URL,
            credentials: staticCreds(),
            context: testContext(),
            retry: { limit: 0 },
        });

        const promise = platformMutator(
            { url: 'api/CreateTenant', method: 'POST', data: {} },
            { http: kyInstance },
        );

        await expect(promise).rejects.toBeInstanceOf(InvalidArgumentError);
        await promise.catch((error: unknown) => {
            const e = error as InvalidArgumentError;
            expect(e.fieldErrors?.tenantId).toEqual(['Required']);
        });
    });

    it('forwards options.signal to abort the request', async () => {
        let resolved = false;
        server.use(
            http.post(`${BASE_URL}/api/Slow`, async () => {
                await new Promise((r) => setTimeout(r, 200));
                resolved = true;
                return HttpResponse.json({});
            }),
        );

        const kyInstance = testKy();
        const controller = new AbortController();
        setTimeout(() => controller.abort(), 10);

        await expect(
            platformMutator(
                { url: 'api/Slow', method: 'POST' },
                { http: kyInstance, signal: controller.signal },
            ),
        ).rejects.toBeDefined();
        expect(resolved).toBe(false);
    });
});
