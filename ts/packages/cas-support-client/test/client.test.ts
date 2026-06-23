import {
    AlreadyExistsError,
    InvalidArgumentError,
    TokenGrantCredentials,
    type AccessToken,
    type ClientContext,
    type Credentials,
} from '@onenexus-team/sdk-core';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from 'vitest';

import { CasSupportClient } from '../src/client.js';

const BASE_URL = 'https://cas.test.invalid';

function staticCreds(label = 'static'): Credentials {
    return new TokenGrantCredentials({
        token: {
            accessToken: `at-${label}`,
            tokenType: 'Bearer',
            expiresAt: new Date('2030-01-01T00:00:00Z'),
        },
    });
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

describe('CasSupportClient', () => {
    describe('happy path', () => {
        it('createTenant POSTs to /support-api/CreateTenant with the request body and Bearer auth, parses the response', async () => {
            let observedBody: unknown;
            let observedAuth: string | null = null;

            server.use(
                http.post(`${BASE_URL}/support-api/CreateTenant`, async ({ request }) => {
                    observedAuth = request.headers.get('authorization');
                    observedBody = await request.json();
                    return HttpResponse.json({
                        tenantId: 'tn_acme',
                    });
                }),
            );

            const support = new CasSupportClient({
                baseUrl: BASE_URL,
                credentials: staticCreds('happy'),
            });
            const result = await support.createTenant({
                name: 'tn_acme',
                displayName: 'Acme Inc',
                clientToken: '01HV8XR4D0YPRNNK8YY8VJ3QK2',
            });

            expect(result.tenantId).toBe('tn_acme');
            expect(observedAuth).toBe('Bearer at-happy');
            expect(observedBody).toEqual({
                name: 'tn_acme',
                displayName: 'Acme Inc',
                clientToken: '01HV8XR4D0YPRNNK8YY8VJ3QK2',
            });
        });

        it('describeTenant and addTenantUser bind through the same transport', async () => {
            server.use(
                http.post(`${BASE_URL}/support-api/DescribeTenant`, () =>
                    HttpResponse.json({
                        data: {
                            tenantId: '0193fabc-1234-7def-abcd-1234567890ab',
                            name: 'tn_acme',
                            displayName: 'Acme Inc',
                            status: 1,
                            userCount: 3,
                            createdAt: '2026-05-13T10:00:00Z',
                        },
                    }),
                ),
                http.post(`${BASE_URL}/support-api/AddTenantUser`, () =>
                    HttpResponse.json({
                        user: {
                            userId: '0193fabc-1234-7def-abcd-1234567890ab',
                            tenantId: '0193fabc-1234-7def-abcd-1234567890ac',
                            email: 'a@b.c',
                            displayName: 'A B',
                            emailConfirmed: false,
                            createdAt: '2026-05-13T10:00:00Z',
                        },
                        acceptInvitationUrl: 'https://portal.acme.com/user/accept?token=abc',
                        acceptInvitationExpiresAt: '2026-05-20T10:00:00Z',
                    }),
                ),
            );

            const support = new CasSupportClient({ baseUrl: BASE_URL, credentials: staticCreds() });

            const tenant = await support.describeTenant({
                tenantId: '0193fabc-1234-7def-abcd-1234567890ab',
            });
            expect(tenant.data.userCount).toBe(3);

            const created = await support.addTenantUser({
                name: 'a',
                email: 'a@b.c',
                displayName: 'A B',
                clientToken: '01HV8XR4D0YPRNNK8YY8VJ3QK2',
            });
            expect(created.user.email).toBe('a@b.c');
            expect(created.acceptInvitationUrl).toContain('token=abc');
        });
    });

    describe('error mapping', () => {
        it('translates a 409 with already_exists into AlreadyExistsError', async () => {
            server.use(
                http.post(`${BASE_URL}/support-api/CreateTenant`, () =>
                    HttpResponse.json(
                        {
                            type: 'https://docs.onenexus.vn/errors/already-exists',
                            title: 'Tenant already exists',
                            status: 409,
                            detail: "Tenant 'tn_acme' already exists.",
                            instance: '/support-api/CreateTenant',
                            code: 'already_exists',
                            requestId: 'trace-conflict',
                        },
                        { status: 409, headers: { 'content-type': 'application/problem+json' } },
                    ),
                ),
            );

            const support = new CasSupportClient({
                baseUrl: BASE_URL,
                credentials: staticCreds(),
                retry: { limit: 0 },
            });

            const promise = support.createTenant({
                name: 'tn_acme',
                displayName: 'Acme',
                clientToken: '01HV8XR4D0YPRNNK8YY8VJ3QK2',
            });

            await expect(promise).rejects.toBeInstanceOf(AlreadyExistsError);
            await promise.catch((error: unknown) => {
                const e = error as AlreadyExistsError;
                expect(e.code).toBe('already_exists');
                expect(e.requestId).toBe('trace-conflict');
                expect(e.detail).toBe("Tenant 'tn_acme' already exists.");
            });
        });

        it('translates a 400 with field errors into InvalidArgumentError with fieldErrors populated', async () => {
            server.use(
                http.post(`${BASE_URL}/support-api/CreateTenant`, () =>
                    HttpResponse.json(
                        {
                            code: 'invalid_argument',
                            status: 400,
                            detail: 'See errors for per-field details.',
                            errors: { name: ['Required.'], displayName: ['Required.'] },
                        },
                        { status: 400, headers: { 'content-type': 'application/problem+json' } },
                    ),
                ),
            );

            const support = new CasSupportClient({
                baseUrl: BASE_URL,
                credentials: staticCreds(),
                retry: { limit: 0 },
            });

            const promise = support.createTenant({
                name: '',
                displayName: '',
                clientToken: '01HV8XR4D0YPRNNK8YY8VJ3QK2',
            });

            await expect(promise).rejects.toBeInstanceOf(InvalidArgumentError);
            await promise.catch((error: unknown) => {
                const e = error as InvalidArgumentError;
                expect(e.fieldErrors).toEqual({
                    name: ['Required.'],
                    displayName: ['Required.'],
                });
            });
        });
    });

    describe('401 retry with server-clock update', () => {
        it('end-to-end through CasSupportClient: first 401 records server time; retry resolves fresh token and succeeds', async () => {
            const stale: AccessToken = {
                accessToken: 'at-stale',
                tokenType: 'Bearer',
                expiresAt: new Date('2030-01-01T00:00:00Z'),
            };
            const fresh: AccessToken = { ...stale, accessToken: 'at-fresh' };
            const cutoff = Date.now() + 60_000;

            const credentials: Credentials = {
                resolve: vi.fn((context: ClientContext) =>
                    Promise.resolve(context.clock.serverNow() >= cutoff ? fresh : stale),
                ),
            };

            const observedAuth: string[] = [];
            let serverCallCount = 0;

            server.use(
                http.post(`${BASE_URL}/support-api/CreateTenant`, ({ request }) => {
                    observedAuth.push(request.headers.get('authorization') ?? '');
                    serverCallCount += 1;
                    if (serverCallCount === 1) {
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
                    return HttpResponse.json({
                        tenantId: 'tn_acme',
                    });
                }),
            );

            const support = new CasSupportClient({ baseUrl: BASE_URL, credentials });
            const result = await support.createTenant({
                name: 'tn_acme',
                displayName: 'Acme',
                clientToken: '01HV8XR4D0YPRNNK8YY8VJ3QK2',
            });

            expect(result.tenantId).toBe('tn_acme');
            expect(observedAuth).toEqual(['Bearer at-stale', 'Bearer at-fresh']);
            expect(credentials.resolve).toHaveBeenCalledTimes(2);
        });
    });

    describe('cancellation', () => {
        it('aborts an in-flight request when the caller-supplied signal fires', async () => {
            let serverResolved = false;
            server.use(
                http.post(`${BASE_URL}/support-api/CreateTenant`, async () => {
                    await new Promise((r) => setTimeout(r, 250));
                    serverResolved = true;
                    return HttpResponse.json({
                        tenantId: 'tn_acme',
                    });
                }),
            );

            const support = new CasSupportClient({ baseUrl: BASE_URL, credentials: staticCreds() });
            const controller = new AbortController();
            setTimeout(() => controller.abort(), 10);

            await expect(
                support.createTenant(
                    {
                        name: 'tn_acme',
                        displayName: 'Acme',
                        clientToken: '01HV8XR4D0YPRNNK8YY8VJ3QK2',
                    },
                    { signal: controller.signal },
                ),
            ).rejects.toBeDefined();
            expect(serverResolved).toBe(false);
        });
    });

    describe('instance isolation', () => {
        it('two clients with different credentials do not share auth state', async () => {
            const observed: string[] = [];

            server.use(
                http.post(`${BASE_URL}/support-api/CreateTenant`, ({ request }) => {
                    observed.push(request.headers.get('authorization') ?? '');
                    return HttpResponse.json({
                        tenantId: 'tn_acme',
                    });
                }),
            );

            const supportA = new CasSupportClient({
                baseUrl: BASE_URL,
                credentials: staticCreds('userA'),
            });
            const supportB = new CasSupportClient({
                baseUrl: BASE_URL,
                credentials: staticCreds('userB'),
            });

            // Issue concurrently to ensure no module-level state can leak
            // between them under race conditions.
            await Promise.all([
                supportA.createTenant({
                    name: 'tn_a',
                    displayName: 'A',
                    clientToken: '01HV8XR4D0YPRNNK8YY8VJ3QK2',
                }),
                supportB.createTenant({
                    name: 'tn_b',
                    displayName: 'B',
                    clientToken: '01HV8XR4D0YPRNNK8YY8VJ3QK3',
                }),
            ]);

            expect(observed).toHaveLength(2);
            expect(new Set(observed)).toEqual(new Set(['Bearer at-userA', 'Bearer at-userB']));
        });
    });

    describe('method binding ergonomics', () => {
        it('methods are auto-bound — destructuring keeps `this`', async () => {
            server.use(
                http.post(`${BASE_URL}/support-api/CreateTenant`, () =>
                    HttpResponse.json({
                        tenantId: 'tn_x',
                    }),
                ),
            );

            const support = new CasSupportClient({ baseUrl: BASE_URL, credentials: staticCreds() });
            const { createTenant } = support;

            const result = await createTenant({
                name: 'tn_x',
                displayName: 'X',
                clientToken: '01HV8XR4D0YPRNNK8YY8VJ3QK2',
            });
            expect(result.tenantId).toBe('tn_x');
        });
    });
});
