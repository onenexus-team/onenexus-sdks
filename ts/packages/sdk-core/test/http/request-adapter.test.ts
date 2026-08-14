import { HttpMethod, RequestInformation } from '@microsoft/kiota-abstractions';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from 'vitest';

import type { AccessToken, Credentials } from '../../src/credentials/credentials.js';
import {
    createRequestAdapter,
    createRequestConfiguration,
    OneNexusAuthenticationProvider,
} from '../../src/http/request-adapter.js';
import { testContext } from '../helpers/context.js';

const BASE_URL = 'https://cas.test.invalid';

function token(label: string): AccessToken {
    return {
        accessToken: `at-${label}`,
        tokenType: 'Bearer',
        expiresAt: new Date('2030-01-01T00:00:00Z'),
    };
}

function makeCredentials(): Credentials & { resolve: ReturnType<typeof vi.fn> } {
    return { resolve: vi.fn().mockResolvedValue(token('test')) };
}

function postRequest(path: string, body: unknown, signal?: AbortSignal): RequestInformation {
    const request = new RequestInformation(HttpMethod.POST, `{+baseurl}${path}`, {});
    request.headers.add('content-type', 'application/json');
    request.headers.add('x-request-id', 'stable-request-id');
    request.setStreamContent(
        new TextEncoder().encode(JSON.stringify(body)).buffer,
        'application/json',
    );
    request.addRequestOptions(
        createRequestConfiguration(body, signal === undefined ? undefined : { signal }).options,
    );
    return request;
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

describe('OneNexusAuthenticationProvider', () => {
    it('refuses to resolve or attach credentials for a non-allowed host', async () => {
        const credentials = makeCredentials();
        const provider = new OneNexusAuthenticationProvider(
            credentials,
            testContext(),
            'cas.test.invalid',
        );
        const request = new RequestInformation();
        request.URL = 'https://attacker.invalid/api/Op';

        await expect(provider.authenticateRequest(request)).rejects.toThrow(/non-allowed host/);
        expect(credentials.resolve).not.toHaveBeenCalled();
        expect(request.headers.has('authorization')).toBe(false);
    });
});

describe('createRequestAdapter', () => {
    it('uses Kiota native retry for POST while preserving auth, headers, and body', async () => {
        vi.spyOn(Math, 'random').mockReturnValue(0);
        const context = testContext();
        const credentials = makeCredentials();
        const attempts: Array<{
            authorization: string | null;
            contentType: string | null;
            requestId: string | null;
            body: unknown;
        }> = [];
        let callCount = 0;
        const serverDate = new Date(Date.now() + 120_000);

        server.use(
            http.post(`${BASE_URL}/api/Op`, async ({ request }) => {
                attempts.push({
                    authorization: request.headers.get('authorization'),
                    contentType: request.headers.get('content-type'),
                    requestId: request.headers.get('x-request-id'),
                    body: await request.json(),
                });
                callCount += 1;
                if (callCount === 1) {
                    return HttpResponse.json(
                        { type: 'https://docs.onenexus.vn/errors/unavailable', detail: 'retry' },
                        { status: 503, headers: { date: serverDate.toUTCString() } },
                    );
                }
                return new HttpResponse(null, { status: 204 });
            }),
        );

        const adapter = createRequestAdapter({
            baseUrl: BASE_URL,
            credentials,
            context,
            retry: { limit: 1, backoffLimitMs: 0 },
        });
        await adapter.sendNoResponseContent(postRequest('/api/Op', { value: 'stable' }), undefined);

        expect(attempts).toEqual([
            {
                authorization: 'Bearer at-test',
                contentType: 'application/json',
                requestId: 'stable-request-id',
                body: { value: 'stable' },
            },
            {
                authorization: 'Bearer at-test',
                contentType: 'application/json',
                requestId: 'stable-request-id',
                body: { value: 'stable' },
            },
        ]);
        expect(credentials.resolve).toHaveBeenCalledOnce();
        expect(context.clock.serverNow()).toBeGreaterThan(Date.now() + 110_000);
    });

    it('passes the caller signal to credential resolution and aborts the fetch', async () => {
        const credentials = makeCredentials();
        let serverResolved = false;
        server.use(
            http.post(`${BASE_URL}/api/Slow`, async () => {
                await new Promise((resolve) => setTimeout(resolve, 200));
                serverResolved = true;
                return new HttpResponse(null, { status: 204 });
            }),
        );

        const adapter = createRequestAdapter({
            baseUrl: BASE_URL,
            credentials,
            context: testContext(),
            retry: { limit: 0 },
        });
        const controller = new AbortController();
        setTimeout(() => controller.abort(), 10);
        const request = postRequest('/api/Slow', {}, controller.signal);

        await expect(adapter.sendNoResponseContent(request, undefined)).rejects.toBeDefined();
        expect(credentials.resolve).toHaveBeenCalledWith(expect.anything(), controller.signal);
        expect(serverResolved).toBe(false);
    });
});
