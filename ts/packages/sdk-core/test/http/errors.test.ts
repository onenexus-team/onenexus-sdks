import { DefaultApiError } from '@microsoft/kiota-abstractions';
import { describe, expect, it } from 'vitest';

import {
    AlreadyExistsError,
    FailedPreconditionError,
    ForbiddenError,
    InternalError,
    InvalidArgumentError,
    NotFoundError,
    parseHttpError,
    parseHttpResponseError,
    PlatformError,
    ResourceExhaustedError,
    UnauthenticatedError,
    UnavailableError,
} from '../../src/http/errors.js';

function problemResponse(body: unknown, status: number): Response {
    return new Response(JSON.stringify(body), {
        status,
        headers: { 'content-type': 'application/problem+json' },
    });
}

describe('parseHttpResponseError', () => {
    it('maps Problem Details extensions into shared error fields', async () => {
        const parsed = await parseHttpResponseError(
            problemResponse(
                {
                    type: 'https://docs.onenexus.vn/errors/invalid-argument',
                    title: 'Validation failed',
                    status: 400,
                    detail: 'See errors for details.',
                    instance: '/api/CreateTenant',
                    code: 'invalid_argument',
                    requestId: 'trace-123',
                    errors: { tenantId: ['Required'], ignored: [1] },
                },
                400,
            ),
        );

        expect(parsed).toBeInstanceOf(InvalidArgumentError);
        expect(parsed).toMatchObject({
            code: 'invalid_argument',
            status: 400,
            detail: 'See errors for details.',
            requestId: 'trace-123',
            instance: '/api/CreateTenant',
            fieldErrors: { tenantId: ['Required'] },
        });
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
    ] as const)('maps %s to its matching subclass', async (code, status, ErrorType) => {
        const parsed = await parseHttpResponseError(
            problemResponse({ code, detail: `${code} happened` }, status),
        );
        expect(parsed).toBeInstanceOf(ErrorType);
        expect(parsed?.code).toBe(code);
    });

    it('derives the code from the problem type URI', async () => {
        const parsed = await parseHttpResponseError(
            problemResponse(
                {
                    type: 'https://docs.onenexus.vn/errors/failed-precondition',
                    detail: 'state changed',
                },
                409,
            ),
        );
        expect(parsed).toBeInstanceOf(FailedPreconditionError);
    });

    it('falls back to PlatformError for unknown codes', async () => {
        const parsed = await parseHttpResponseError(
            problemResponse({ code: 'something_unexpected', detail: 'teapot' }, 418),
        );
        expect(parsed).toBeInstanceOf(PlatformError);
        expect(parsed).not.toBeInstanceOf(InvalidArgumentError);
    });

    it('does not consume non-Problem-Details failures', async () => {
        const response = new Response('<html>bad gateway</html>', {
            status: 502,
            headers: { 'content-type': 'text/html' },
        });
        await expect(parseHttpResponseError(response)).resolves.toBeUndefined();
        await expect(response.text()).resolves.toBe('<html>bad gateway</html>');
    });
});

describe('parseHttpError', () => {
    it('passes non-Kiota errors through unchanged', async () => {
        const networkError = new TypeError('fetch failed');
        await expect(parseHttpError(networkError)).resolves.toBe(networkError);
    });

    it('maps an unmapped Kiota error by response status', async () => {
        const error = new DefaultApiError('missing');
        error.responseStatusCode = 404;
        const parsed = await parseHttpError(error);
        expect(parsed).toBeInstanceOf(NotFoundError);
        expect((parsed as NotFoundError).detail).toBe('missing');
    });
});
