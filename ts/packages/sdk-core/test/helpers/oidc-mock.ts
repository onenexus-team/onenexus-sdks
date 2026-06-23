/**
 * Mock OIDC server helpers for credential tests.
 *
 * Spins up MSW handlers for the OIDC discovery document and token endpoint
 * so credential implementations that use `openid-client` can exercise their
 * full discovery + grant flow without contacting a real auth server.
 *
 * Two URLs are intercepted:
 *
 * - `GET <issuer>/.well-known/openid-configuration` — returns OIDC server
 *   metadata pointing token/authorization/jwks endpoints back at the same
 *   mock host.
 * - `POST <issuer>/token` — accepts the form-encoded grant request and
 *   replies with a `TokenEndpointResponse`-shaped JSON body. Tests configure
 *   the response (or sequence of responses) via {@link MockOidcServer.queueTokenResponse}.
 *
 * Every token request is recorded on the server instance so tests can assert
 * on grant type, scope, and so on.
 */

import { http, HttpResponse, type DefaultBodyType, type StrictRequest } from 'msw';
import { setupServer, type SetupServerApi } from 'msw/node';

/** Shape of a successful token-endpoint reply. Field names match RFC 6749. */
export interface MockTokenResponse {
    readonly access_token: string;
    readonly token_type?: string;
    readonly expires_in?: number;
    readonly refresh_token?: string;
    readonly id_token?: string;
    readonly scope?: string;
    /** Allow arbitrary extra fields without widening the type. */
    readonly [extra: string]: unknown;
}

/** Shape of an OAuth/OIDC error reply. */
export interface MockTokenError {
    readonly error: string;
    readonly error_description?: string;
    readonly status?: number; // defaults to 400
}

/** Recorded inbound token-endpoint request, parsed into form fields. */
export interface RecordedTokenRequest {
    readonly headers: Headers;
    readonly form: Record<string, string>;
}

export interface MockOidcServer {
    /** The MSW server. Tests must call `server.listen()` / `.close()` themselves. */
    readonly server: SetupServerApi;
    /** Issuer URL the mock advertises. Pass this to the credential under test. */
    readonly issuer: string;
    /**
     * Queue a token response. Calls are consumed FIFO; the next inbound
     * `POST /token` returns the head of the queue.
     */
    queueTokenResponse(response: MockTokenResponse | MockTokenError): void;
    /** Every token-endpoint hit observed so far, in order. */
    readonly tokenRequests: readonly RecordedTokenRequest[];
    /** Reset queued responses + recorded requests between tests. */
    reset(): void;
}

const DEFAULT_ISSUER = 'https://cas.test.invalid';

export function createMockOidcServer(issuer: string = DEFAULT_ISSUER): MockOidcServer {
    const responseQueue: Array<MockTokenResponse | MockTokenError> = [];
    const recorded: RecordedTokenRequest[] = [];

    function isError(value: MockTokenResponse | MockTokenError): value is MockTokenError {
        return 'error' in value;
    }

    async function readForm(
        request: StrictRequest<DefaultBodyType>,
    ): Promise<Record<string, string>> {
        const body = await request.text();
        const params = new URLSearchParams(body);
        return Object.fromEntries(params.entries());
    }

    const handlers = [
        http.get(`${issuer}/.well-known/openid-configuration`, () =>
            HttpResponse.json({
                issuer,
                token_endpoint: `${issuer}/token`,
                authorization_endpoint: `${issuer}/authorize`,
                end_session_endpoint: `${issuer}/logout`,
                jwks_uri: `${issuer}/jwks`,
                response_types_supported: ['code'],
                subject_types_supported: ['public'],
                id_token_signing_alg_values_supported: ['RS256'],
                grant_types_supported: [
                    'authorization_code',
                    'refresh_token',
                    'client_credentials',
                ],
                token_endpoint_auth_methods_supported: ['private_key_jwt', 'none'],
                code_challenge_methods_supported: ['S256'],
            }),
        ),
        http.get(`${issuer}/jwks`, () => HttpResponse.json({ keys: [] })),
        http.post(`${issuer}/token`, async ({ request }) => {
            recorded.push({
                headers: new Headers(request.headers),
                form: await readForm(request),
            });
            const next = responseQueue.shift();
            if (next === undefined) {
                return HttpResponse.json(
                    {
                        error: 'server_error',
                        error_description:
                            'mock OIDC server: no queued response — test should call queueTokenResponse() before triggering the grant',
                    },
                    { status: 500 },
                );
            }
            if (isError(next)) {
                const { status = 400, ...body } = next;
                return HttpResponse.json(body, { status });
            }
            // oauth4webapi requires `token_type` per RFC 6749 §5.1 — default it
            // to 'Bearer' so tests don't have to repeat it on every queued
            // response.
            return HttpResponse.json({ token_type: 'Bearer', ...next });
        }),
    ];

    const server = setupServer(...handlers);

    return {
        server,
        issuer,
        queueTokenResponse: (response) => responseQueue.push(response),
        tokenRequests: recorded,
        reset: () => {
            responseQueue.length = 0;
            recorded.length = 0;
        },
    };
}
