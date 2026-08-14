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

import { CasClient } from '../src/client.js';

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

const userResponse = (overrides?: { tenantId?: string; email?: string; displayName?: string }) => ({
    user: {
        userId: '0193fabc-1234-7def-abcd-1234567890ab',
        userUri: 'onenexus:user/0193fabc-1234-7def-abcd-1234567890ab',
        tenantId: overrides?.tenantId ?? 'tn_acme',
        email: overrides?.email ?? 'a@b.c',
        displayName: overrides?.displayName ?? 'A B',
        emailConfirmed: false,
        createdAt: '2026-05-13T10:00:00Z',
    },
});

const server = setupServer();
beforeAll(() => {
    server.listen({ onUnhandledRequest: 'error' });
});
afterEach(() => {
    vi.restoreAllMocks();
    server.resetHandlers();
});
afterAll(() => {
    server.close();
});

describe('CasClient', () => {
    describe('happy path', () => {
        it('createUser POSTs to /api/CreateUser with the request body and Bearer auth, parses the response', async () => {
            let observedBody: unknown;
            let observedAuth: string | null = null;

            server.use(
                http.post(`${BASE_URL}/api/CreateUser`, async ({ request }) => {
                    observedAuth = request.headers.get('authorization');
                    observedBody = await request.json();
                    return HttpResponse.json(userResponse());
                }),
            );

            const cas = new CasClient({ baseUrl: BASE_URL, credentials: staticCreds('happy') });
            const result = await cas.createUser({
                email: 'a@b.c',
                displayName: 'A B',
            });

            expect(result.user.email).toBe('a@b.c');
            expect(observedAuth).toBe('Bearer at-happy');
            expect(observedBody).toEqual({
                email: 'a@b.c',
                displayName: 'A B',
            });
        });

        it('updateProfile adds one idempotency key and reuses it across Ky retries', async () => {
            const idempotencyKey = '0193fabc-1234-7def-abcd-1234567890ab';
            const randomUUID = vi
                .spyOn(globalThis.crypto, 'randomUUID')
                .mockReturnValue(idempotencyKey);
            const observedKeys: string[] = [];
            let requestCount = 0;

            server.use(
                http.post(`${BASE_URL}/account/profile`, ({ request }) => {
                    observedKeys.push(request.headers.get('x-nx1-idempotency-key') ?? '');
                    requestCount += 1;
                    if (requestCount < 3) {
                        return HttpResponse.json({ code: 'unavailable' }, { status: 503 });
                    }
                    return HttpResponse.json({ displayName: 'Updated Name' });
                }),
            );

            const cas = new CasClient({
                baseUrl: BASE_URL,
                credentials: staticCreds(),
                retry: { limit: 2, backoffLimitMs: 0 },
            });
            const result = await cas.updateProfile({
                updateMask: ['displayName'],
                displayName: 'Updated Name',
            });

            expect(result.displayName).toBe('Updated Name');
            expect(idempotencyKey).toMatch(/^[a-zA-Z0-9_.-]{16,128}$/);
            expect(observedKeys).toEqual([idempotencyKey, idempotencyKey, idempotencyKey]);
            expect(randomUUID).toHaveBeenCalledTimes(1);
        });

        it('passes client-level refreshLeewayMs through ClientBase context', async () => {
            server.use(
                http.post(`${BASE_URL}/api/CreateUser`, () => HttpResponse.json(userResponse())),
            );

            const token: AccessToken = {
                accessToken: 'at-soon-stale',
                tokenType: 'Bearer',
                expiresAt: new Date(Date.now() + 60_000),
            };
            const credentials = new TokenGrantCredentials({ token });
            const cas = new CasClient({
                baseUrl: BASE_URL,
                credentials,
                refreshLeewayMs: 120_000,
            });

            await expect(
                cas.createUser({
                    email: 'a@b.c',
                    displayName: 'A B',
                }),
            ).rejects.toThrow(/stale/i);
        });

        it('wraps service-client key management and invitation resend operations', async () => {
            const observedBodies = new Map<string, unknown>();
            const serviceClient = {
                id: 'client-1',
                uri: 'onenexus:service-client/client-1',
                clientId: 'client-id-1',
                displayName: 'Automation',
                keys: [],
                lifecycleState: 'Active',
            };

            server.use(
                http.post(`${BASE_URL}/api/RemoveServiceClientKey`, async ({ request }) => {
                    observedBodies.set('removeKey', await request.json());
                    return HttpResponse.json({ serviceClient });
                }),
                http.post(`${BASE_URL}/api/DisableServiceClient`, async ({ request }) => {
                    observedBodies.set('disable', await request.json());
                    return HttpResponse.json({
                        serviceClient: { ...serviceClient, lifecycleState: 'Disabled' },
                    });
                }),
                http.post(`${BASE_URL}/api/ResendUserInvitation`, async ({ request }) => {
                    observedBodies.set('resendInvitation', await request.json());
                    return new HttpResponse(null, { status: 204 });
                }),
            );

            const cas = new CasClient({ baseUrl: BASE_URL, credentials: staticCreds() });
            await expect(
                cas.removeServiceClientKey({ serviceClientId: 'client-1', kid: 'key-1' }),
            ).resolves.toMatchObject({ serviceClient });
            await expect(
                cas.disableServiceClient({ serviceClientId: 'client-1' }),
            ).resolves.toMatchObject({
                serviceClient: { lifecycleState: 'Disabled' },
            });
            await expect(
                cas.resendUserInvitation({ userId: '0193fabc-1234-7def-abcd-1234567890ab' }),
            ).resolves.toBeUndefined();

            expect(observedBodies).toEqual(
                new Map<string, unknown>([
                    ['removeKey', { serviceClientId: 'client-1', kid: 'key-1' }],
                    ['disable', { serviceClientId: 'client-1' }],
                    ['resendInvitation', { userId: '0193fabc-1234-7def-abcd-1234567890ab' }],
                ]),
            );
        });

        it('acceptInvitation binds through the same transport', async () => {
            server.use(
                http.post(`${BASE_URL}/api/AcceptInvitation`, () =>
                    HttpResponse.json({
                        userId: '0193fabc-1234-7def-abcd-1234567890ab',
                        tenantId: 'tn_acme',
                        email: 'a@b.c',
                        loginUrl: 'https://portal.acme.com/user/login?tenant=tn_acme',
                    }),
                ),
            );

            const cas = new CasClient({ baseUrl: BASE_URL, credentials: staticCreds() });

            const user = await cas.acceptInvitation({
                userId: '0193fabc-1234-7def-abcd-1234567890ab',
                token: 'invite-token-abc',
                password: 'a-good-password',
            });
            expect(user.email).toBe('a@b.c');
            expect(user.loginUrl).toContain('tn_acme');
        });

        it('binds authorization policy methods to their generated RPC operations', async () => {
            const observedBodies = new Map<string, unknown>();
            const summary = {
                kind: 'TenantManaged',
                name: 'ReadOnly',
                description: 'Read-only access',
                status: 'Published',
                documentHash: 'sha256:abc',
                contentStateToken: 'state-1',
            };

            server.use(
                http.post(`${BASE_URL}/api/PublishPolicy`, async ({ request }) => {
                    observedBodies.set('publish', await request.json());
                    return HttpResponse.json({
                        kind: 'TenantManaged',
                        disposition: 'Published',
                        reasonCode: 'published',
                        diagnostics: [],
                        contentStateToken: 'state-1',
                    });
                }),
                http.post(`${BASE_URL}/api/ListPolicies`, async ({ request }) => {
                    observedBodies.set('list', await request.json());
                    return HttpResponse.json({ items: [summary] });
                }),
                http.post(`${BASE_URL}/api/GetPolicy`, async ({ request }) => {
                    observedBodies.set('get', await request.json());
                    return HttpResponse.json({
                        policy: {
                            ...summary,
                            document: { Version: '2012-10-17' },
                            createdByUri: 'onenexus:user/user-1',
                            updatedByUri: 'onenexus:user/user-1',
                        },
                    });
                }),
                http.post(`${BASE_URL}/api/UpdatePolicy`, async ({ request }) => {
                    observedBodies.set('update', await request.json());
                    return HttpResponse.json({
                        kind: 'TenantManaged',
                        disposition: 'Published',
                        reasonCode: 'updated',
                        diagnostics: [],
                        contentStateToken: 'state-2',
                    });
                }),
                http.post(`${BASE_URL}/api/DeletePolicy`, async ({ request }) => {
                    observedBodies.set('delete', await request.json());
                    return HttpResponse.json({ name: 'ReadOnly' });
                }),
            );

            const cas = new CasClient({ baseUrl: BASE_URL, credentials: staticCreds() });
            const publishRequest = {
                name: 'ReadOnly',
                description: 'Read-only access',
                document: { Version: '2012-10-17' },
            };

            const published = await cas.publishPolicy(publishRequest);
            const listed = await cas.listPolicies({ limit: 25, after: 'policy-previous' });
            const fetched = await cas.getPolicy({ kind: 'TenantManaged', name: 'ReadOnly' });
            const updated = await cas.updatePolicy({
                ...publishRequest,
                expectedContentStateToken: 'state-1',
            });
            const deleted = await cas.deletePolicy({
                name: 'ReadOnly',
                expectedContentStateToken: 'state-2',
            });

            expect(published.contentStateToken).toBe('state-1');
            expect(listed.items).toEqual([summary]);
            expect(fetched.policy.createdByUri).toBe('onenexus:user/user-1');
            expect(updated.contentStateToken).toBe('state-2');
            expect(deleted.name).toBe('ReadOnly');
            expect(observedBodies).toEqual(
                new Map<string, unknown>([
                    ['publish', publishRequest],
                    ['list', { limit: 25, after: 'policy-previous' }],
                    ['get', { kind: 'TenantManaged', name: 'ReadOnly' }],
                    [
                        'update',
                        {
                            ...publishRequest,
                            expectedContentStateToken: 'state-1',
                        },
                    ],
                    [
                        'delete',
                        {
                            name: 'ReadOnly',
                            expectedContentStateToken: 'state-2',
                        },
                    ],
                ]),
            );
        });

        it('binds role, relationship, and user-list methods to generated RPC operations', async () => {
            const roleUri = 'onenexus:role/Reader';
            const assignee = { kind: 'User' as const, uri: 'onenexus:user/user-1' };
            const policy = { kind: 'TenantManaged' as const, name: 'ReadOnly' };
            const role = { roleUri, name: 'Reader' };
            const assignment = {
                assignmentId: 'assignment-1',
                roleUri,
                assignee,
                stateToken: 'assignment-state-1',
                assignedByUri: 'onenexus:user/admin-1',
                assignedAtUtc: '2026-07-18T10:00:00Z',
            };
            const attachment = {
                attachmentId: 'attachment-1',
                policy,
                roleUri,
                stateToken: 'attachment-state-1',
                attachedByUri: 'onenexus:user/admin-1',
                attachedAtUtc: '2026-07-18T10:00:00Z',
            };
            const observedOperations: string[] = [];
            const respond = (operation: string, body: object) => {
                observedOperations.push(operation);
                return HttpResponse.json(body);
            };

            server.use(
                http.post(`${BASE_URL}/api/CreateRole`, () =>
                    respond('CreateRole', { created: true, role }),
                ),
                http.post(`${BASE_URL}/api/UpdateRoleDescription`, async ({ request }) => {
                    observedOperations.push(
                        `UpdateRoleDescription:${JSON.stringify(await request.json())}`,
                    );
                    return HttpResponse.json({
                        role: { ...role, description: 'Read-only access' },
                    });
                }),
                http.post(`${BASE_URL}/api/ListRoles`, () =>
                    respond('ListRoles', { items: [role] }),
                ),
                http.post(`${BASE_URL}/api/DeleteRole`, () =>
                    respond('DeleteRole', { removed: true, roleUri }),
                ),
                http.post(`${BASE_URL}/api/AssignRole`, () =>
                    respond('AssignRole', { created: true, assignment }),
                ),
                http.post(`${BASE_URL}/api/RemoveRoleAssignment`, () =>
                    respond('RemoveRoleAssignment', { removed: true }),
                ),
                http.post(`${BASE_URL}/api/ListRoleAssignments`, () =>
                    respond('ListRoleAssignments', { items: [assignment] }),
                ),
                http.post(`${BASE_URL}/api/AttachPolicyToRole`, () =>
                    respond('AttachPolicyToRole', { created: true, attachment }),
                ),
                http.post(`${BASE_URL}/api/DetachPolicyFromRole`, () =>
                    respond('DetachPolicyFromRole', { removed: true }),
                ),
                http.post(`${BASE_URL}/api/ListPolicyAttachments`, () =>
                    respond('ListPolicyAttachments', { items: [attachment] }),
                ),
                http.post(`${BASE_URL}/api/ListRolePolicies`, () =>
                    respond('ListRolePolicies', { items: [attachment] }),
                ),
                http.post(`${BASE_URL}/api/ListUsers`, () =>
                    respond('ListUsers', {
                        items: [
                            {
                                userId: '0193fabc-1234-7def-abcd-1234567890ab',
                                userUri: 'onenexus:user/user-1',
                                email: 'a@b.c',
                                displayName: 'A B',
                                kind: 'Member',
                                emailConfirmed: true,
                                createdAt: '2026-07-18T10:00:00Z',
                            },
                        ],
                    }),
                ),
            );

            const cas = new CasClient({ baseUrl: BASE_URL, credentials: staticCreds() });
            expect(await cas.createRole({ name: 'Reader' })).toMatchObject({ created: true, role });
            expect(
                await cas.updateRoleDescription({
                    roleUri,
                    description: 'Read-only access',
                }),
            ).toMatchObject({ role: { ...role, description: 'Read-only access' } });
            expect((await cas.listRoles()).items).toEqual([role]);
            expect(await cas.deleteRole({ roleUri })).toMatchObject({ removed: true, roleUri });
            expect(await cas.assignRole({ roleUri, assignee })).toMatchObject({
                created: true,
                assignment,
            });
            expect(
                await cas.removeRoleAssignment({
                    roleUri,
                    assignee,
                    expectedStateToken: 'assignment-state-1',
                }),
            ).toEqual({ removed: true });
            expect((await cas.listRoleAssignments({ roleUri })).items).toEqual([assignment]);
            expect(await cas.attachPolicyToRole({ policy, roleUri })).toMatchObject({
                created: true,
                attachment,
            });
            expect(
                await cas.detachPolicyFromRole({
                    policy,
                    roleUri,
                    expectedStateToken: 'attachment-state-1',
                }),
            ).toEqual({ removed: true });
            expect((await cas.listPolicyAttachments({ policy })).items).toEqual([attachment]);
            expect((await cas.listRolePolicies({ roleUri })).items).toEqual([attachment]);
            expect((await cas.listUsers({ limit: 10 })).items[0]?.userUri).toBe(
                'onenexus:user/user-1',
            );
            expect(observedOperations).toEqual([
                'CreateRole',
                'UpdateRoleDescription:{"roleUri":"onenexus:role/Reader","description":"Read-only access"}',
                'ListRoles',
                'DeleteRole',
                'AssignRole',
                'RemoveRoleAssignment',
                'ListRoleAssignments',
                'AttachPolicyToRole',
                'DetachPolicyFromRole',
                'ListPolicyAttachments',
                'ListRolePolicies',
                'ListUsers',
            ]);
        });
    });

    describe('error mapping', () => {
        it('translates a 409 with already_exists into AlreadyExistsError', async () => {
            server.use(
                http.post(`${BASE_URL}/api/CreateUser`, () =>
                    HttpResponse.json(
                        {
                            type: 'https://docs.onenexus.vn/errors/already-exists',
                            title: 'User already exists',
                            status: 409,
                            detail: "User 'a@b.c' already exists.",
                            instance: '/api/CreateUser',
                            code: 'already_exists',
                            requestId: 'trace-conflict',
                        },
                        { status: 409, headers: { 'content-type': 'application/problem+json' } },
                    ),
                ),
            );

            const cas = new CasClient({
                baseUrl: BASE_URL,
                credentials: staticCreds(),
                retry: { limit: 0 },
            });

            const promise = cas.createUser({
                email: 'a@b.c',
                displayName: 'A B',
            });

            await expect(promise).rejects.toBeInstanceOf(AlreadyExistsError);
            await promise.catch((error: unknown) => {
                const e = error as AlreadyExistsError;
                expect(e.code).toBe('already_exists');
                expect(e.requestId).toBe('trace-conflict');
                expect(e.detail).toBe("User 'a@b.c' already exists.");
            });
        });

        it('translates a 400 with field errors into InvalidArgumentError with fieldErrors populated', async () => {
            server.use(
                http.post(`${BASE_URL}/api/CreateUser`, () =>
                    HttpResponse.json(
                        {
                            code: 'invalid_argument',
                            status: 400,
                            detail: 'See errors for per-field details.',
                            errors: { email: ['Required.'], displayName: ['Required.'] },
                        },
                        { status: 400, headers: { 'content-type': 'application/problem+json' } },
                    ),
                ),
            );

            const cas = new CasClient({
                baseUrl: BASE_URL,
                credentials: staticCreds(),
                retry: { limit: 0 },
            });

            const promise = cas.createUser({
                email: '',
                displayName: '',
            });

            await expect(promise).rejects.toBeInstanceOf(InvalidArgumentError);
            await promise.catch((error: unknown) => {
                const e = error as InvalidArgumentError;
                expect(e.fieldErrors).toEqual({
                    email: ['Required.'],
                    displayName: ['Required.'],
                });
            });
        });
    });

    describe('401 retry with server-clock update', () => {
        it('end-to-end through CasClient: first 401 records server time; retry resolves fresh token and succeeds', async () => {
            const stale: AccessToken = {
                accessToken: 'at-stale',
                tokenType: 'Bearer',
                expiresAt: new Date('2030-01-01T00:00:00Z'),
            };
            const fresh: AccessToken = { ...stale, accessToken: 'at-fresh' };
            const cutoff = Date.now() + 60_000;

            const resolve = vi.fn((context: ClientContext) =>
                Promise.resolve(context.clock.serverNow() >= cutoff ? fresh : stale),
            );
            const credentials: Credentials = { resolve };

            const observedAuth: string[] = [];
            let serverCallCount = 0;

            server.use(
                http.post(`${BASE_URL}/api/CreateUser`, ({ request }) => {
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
                    return HttpResponse.json(userResponse());
                }),
            );

            const cas = new CasClient({ baseUrl: BASE_URL, credentials });
            const result = await cas.createUser({
                email: 'a@b.c',
                displayName: 'A B',
            });

            expect(result.user.email).toBe('a@b.c');
            expect(observedAuth).toEqual(['Bearer at-stale', 'Bearer at-fresh']);
            expect(resolve).toHaveBeenCalledTimes(2);
        });
    });

    describe('cancellation', () => {
        it('aborts an in-flight request when the caller-supplied signal fires', async () => {
            let serverResolved = false;
            server.use(
                http.post(`${BASE_URL}/api/CreateUser`, async () => {
                    await new Promise((r) => setTimeout(r, 250));
                    serverResolved = true;
                    return HttpResponse.json(userResponse());
                }),
            );

            const cas = new CasClient({ baseUrl: BASE_URL, credentials: staticCreds() });
            const controller = new AbortController();
            setTimeout(() => controller.abort(), 10);

            await expect(
                cas.createUser(
                    {
                        email: 'a@b.c',
                        displayName: 'A B',
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
                http.post(`${BASE_URL}/api/CreateUser`, ({ request }) => {
                    observed.push(request.headers.get('authorization') ?? '');
                    return HttpResponse.json(userResponse());
                }),
            );

            const casA = new CasClient({ baseUrl: BASE_URL, credentials: staticCreds('userA') });
            const casB = new CasClient({ baseUrl: BASE_URL, credentials: staticCreds('userB') });

            // Issue concurrently to ensure no module-level state can leak
            // between them under race conditions.
            await Promise.all([
                casA.createUser({
                    email: 'a@a.c',
                    displayName: 'A',
                }),
                casB.createUser({
                    email: 'b@b.c',
                    displayName: 'B',
                }),
            ]);

            expect(observed).toHaveLength(2);
            expect(new Set(observed)).toEqual(new Set(['Bearer at-userA', 'Bearer at-userB']));
        });
    });

    describe('method binding ergonomics', () => {
        it('methods are auto-bound — destructuring keeps `this`', async () => {
            server.use(
                http.post(`${BASE_URL}/api/CreateUser`, () =>
                    HttpResponse.json(userResponse({ email: 'x@x.c', displayName: 'X' })),
                ),
            );

            const cas = new CasClient({ baseUrl: BASE_URL, credentials: staticCreds() });
            const { createUser } = cas;

            const result = await createUser({
                email: 'x@x.c',
                displayName: 'X',
            });
            expect(result.user.email).toBe('x@x.c');
        });
    });
});
