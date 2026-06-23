import { HTTPError } from 'ky';
import { describe, expect, it } from 'vitest';

import {
    AlreadyExistsError,
    FailedPreconditionError,
    ForbiddenError,
    InternalError,
    InvalidArgumentError,
    NotFoundError,
    parseHttpError,
    PlatformError,
    ResourceExhaustedError,
    UnauthenticatedError,
    UnavailableError,
} from '../../src/http/errors.js';

/**
 * Synthesise an HTTPError without making a real network call. Ky's HTTPError
 * constructor takes (response, request, options); we only care about response
 * for the error-parsing path.
 */
function makeHttpError(body: unknown, init: { status: number; contentType?: string }): HTTPError {
    const headers = new Headers({
        'content-type': init.contentType ?? 'application/problem+json',
    });
    const response = new Response(typeof body === 'string' ? body : JSON.stringify(body), {
        status: init.status,
        headers,
    });
    const request = new Request('https://example.invalid/api/Op');
    const kyOptions = {
        method: 'POST',
        prefixUrl: '',
        retry: 0,
        timeout: 0,
        hooks: {},
    };
    return new HTTPError(
        response,
        request,
        kyOptions as unknown as ConstructorParameters<typeof HTTPError>[2],
    );
}

describe('parseHttpError', () => {
    it('passes non-HTTPError values through unchanged', async () => {
        const network = new TypeError('fetch failed');
        await expect(parseHttpError(network)).resolves.toBe(network);
    });

    it('maps invalid_argument → InvalidArgumentError with fieldErrors', async () => {
        const error = makeHttpError(
            {
                type: 'https://docs.onenexus.vn/errors/invalid-argument',
                title: 'Validation failed',
                status: 400,
                detail: 'See errors for details.',
                instance: '/api/CreateTenant',
                code: 'invalid_argument',
                requestId: 'trace-123',
                errors: { tenantId: ['Must match ^[a-z0-9]'], name: ['Required'] },
            },
            { status: 400 },
        );
        const parsed = await parseHttpError(error);
        expect(parsed).toBeInstanceOf(InvalidArgumentError);
        const e = parsed as InvalidArgumentError;
        expect(e.code).toBe('invalid_argument');
        expect(e.status).toBe(400);
        expect(e.detail).toBe('See errors for details.');
        expect(e.requestId).toBe('trace-123');
        expect(e.instance).toBe('/api/CreateTenant');
        expect(e.fieldErrors?.tenantId).toEqual(['Must match ^[a-z0-9]']);
        expect(e.name).toBe('InvalidArgumentError');
        expect(e.message).toBe('See errors for details.');
    });

    it.each([
        ['unauthenticated', 401, UnauthenticatedError],
        ['forbidden', 403, ForbiddenError],
        ['not_found', 404, NotFoundError],
        ['already_exists', 409, AlreadyExistsError],
        ['failed_precondition', 409, FailedPreconditionError],
        ['resource_exhausted', 429, ResourceExhaustedError],
        ['unavailable', 503, UnavailableError],
        ['internal', 500, InternalError],
    ] as const)('maps %s → matching subclass', async (code, status, Ctor) => {
        const error = makeHttpError({ code, status, detail: `${code} happened` }, { status });
        const parsed = await parseHttpError(error);
        expect(parsed).toBeInstanceOf(Ctor);
        expect((parsed as PlatformError).code).toBe(code);
    });

    it('falls back to PlatformError for unknown codes', async () => {
        const error = makeHttpError(
            { code: 'something_unexpected', status: 418, detail: 'teapot' },
            { status: 418 },
        );
        const parsed = await parseHttpError(error);
        expect(parsed).toBeInstanceOf(PlatformError);
        expect(parsed).not.toBeInstanceOf(InvalidArgumentError);
        expect((parsed as PlatformError).code).toBe('something_unexpected');
    });

    it('derives code from HTTP status when the body omits it', async () => {
        const error = makeHttpError({ title: 'Not Found' }, { status: 404 });
        const parsed = await parseHttpError(error);
        expect(parsed).toBeInstanceOf(NotFoundError);
        expect((parsed as NotFoundError).code).toBe('not_found');
    });

    it('returns the original HTTPError when the response is not JSON', async () => {
        const error = makeHttpError('<html>not json</html>', {
            status: 502,
            contentType: 'text/html',
        });
        const parsed = await parseHttpError(error);
        expect(parsed).toBe(error);
    });

    it('returns the original HTTPError when the JSON body is not Problem-Details-shaped', async () => {
        const error = makeHttpError(
            { random: 'object' },
            {
                status: 500,
                contentType: 'application/json',
            },
        );
        const parsed = await parseHttpError(error);
        expect(parsed).toBe(error);
    });

    it('accepts application/json content-type for Problem-Details bodies', async () => {
        const error = makeHttpError(
            { code: 'not_found', status: 404, detail: 'gone' },
            { status: 404, contentType: 'application/json' },
        );
        const parsed = await parseHttpError(error);
        expect(parsed).toBeInstanceOf(NotFoundError);
    });
});
