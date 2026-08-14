import type { ApiError } from '@microsoft/kiota-abstractions';

/** Initializer for an RFC 9457 OneNexus platform error. */
export interface PlatformErrorInit {
    readonly code: string;
    readonly status: number;
    readonly detail: string;
    readonly type?: string | undefined;
    readonly title?: string | undefined;
    readonly instance?: string | undefined;
    readonly requestId?: string | undefined;
    readonly fieldErrors?: Readonly<Record<string, readonly string[]>> | undefined;
}

/** Base class for every platform RPC error. */
export class PlatformError extends Error {
    readonly code: string;
    readonly status: number;
    readonly detail: string;
    readonly problemType: string | undefined;
    readonly title: string | undefined;
    readonly instance: string | undefined;
    readonly requestId: string | undefined;
    readonly fieldErrors: Readonly<Record<string, readonly string[]>> | undefined;

    constructor(init: PlatformErrorInit) {
        super(init.detail);
        this.name = new.target.name;
        this.code = init.code;
        this.status = init.status;
        this.detail = init.detail;
        this.problemType = init.type;
        this.title = init.title;
        this.instance = init.instance;
        this.requestId = init.requestId;
        this.fieldErrors = init.fieldErrors;
    }
}

export class InvalidArgumentError extends PlatformError {}
export class UnauthenticatedError extends PlatformError {}
export class ForbiddenError extends PlatformError {}
export class NotFoundError extends PlatformError {}
export class AlreadyExistsError extends PlatformError {}
export class FailedPreconditionError extends PlatformError {}
export class ResourceExhaustedError extends PlatformError {}
export class UnavailableError extends PlatformError {}
export class InternalError extends PlatformError {}

const CODE_TO_CLASS: Readonly<Record<string, new (init: PlatformErrorInit) => PlatformError>> = {
    invalid_argument: InvalidArgumentError,
    unauthenticated: UnauthenticatedError,
    forbidden: ForbiddenError,
    not_found: NotFoundError,
    already_exists: AlreadyExistsError,
    failed_precondition: FailedPreconditionError,
    resource_exhausted: ResourceExhaustedError,
    unavailable: UnavailableError,
    internal: InternalError,
};

function statusToCode(status: number): string {
    if (status === 400) return 'invalid_argument';
    if (status === 401) return 'unauthenticated';
    if (status === 403) return 'forbidden';
    if (status === 404) return 'not_found';
    if (status === 409) return 'already_exists';
    if (status === 429) return 'resource_exhausted';
    if (status >= 500 && status < 600) return status === 503 ? 'unavailable' : 'internal';
    return 'internal';
}

interface ProblemDetailsBody {
    readonly type?: unknown;
    readonly title?: unknown;
    readonly status?: unknown;
    readonly detail?: unknown;
    readonly instance?: unknown;
    readonly code?: unknown;
    readonly requestId?: unknown;
    readonly errors?: unknown;
}

function isObject(value: unknown): value is Record<string, unknown> {
    return typeof value === 'object' && value !== null;
}

function isProblemDetails(value: unknown): value is ProblemDetailsBody {
    return (
        isObject(value) &&
        ('code' in value || 'title' in value || 'detail' in value || 'type' in value)
    );
}

function optionalString(value: unknown): string | undefined {
    return typeof value === 'string' ? value : undefined;
}

function toFieldErrors(value: unknown): Readonly<Record<string, readonly string[]>> | undefined {
    if (!isObject(value)) return undefined;

    const result: Record<string, readonly string[]> = {};
    for (const [field, messages] of Object.entries(value)) {
        if (Array.isArray(messages) && messages.every((message) => typeof message === 'string')) {
            result[field] = messages;
        }
    }
    return Object.keys(result).length > 0 ? result : undefined;
}

function codeFromProblemType(problemType: string | undefined): string | undefined {
    if (problemType === undefined || problemType === 'about:blank') return undefined;
    const segment = problemType.split('/').filter(Boolean).at(-1);
    return segment?.replaceAll('-', '_');
}

function createPlatformError(body: ProblemDetailsBody, responseStatus: number): PlatformError {
    const problemType = optionalString(body.type);
    const status = typeof body.status === 'number' ? body.status : responseStatus;
    const code =
        optionalString(body.code) ??
        codeFromProblemType(problemType) ??
        statusToCode(responseStatus);
    const Ctor = CODE_TO_CLASS[code] ?? PlatformError;
    const title = optionalString(body.title);

    return new Ctor({
        code,
        status,
        detail: optionalString(body.detail) ?? title ?? `HTTP ${responseStatus.toString()}`,
        type: problemType,
        title,
        instance: optionalString(body.instance),
        requestId: optionalString(body.requestId),
        fieldErrors: toFieldErrors(body.errors),
    });
}

/** Parse a failed Fetch response into a shared platform error when possible. */
export async function parseHttpResponseError(
    response: Response,
): Promise<PlatformError | undefined> {
    if (response.ok || response.status < 400) return undefined;

    const contentType = response.headers.get('content-type')?.toLowerCase() ?? '';
    if (
        !contentType.includes('application/json') &&
        !contentType.includes('application/problem+json')
    ) {
        return undefined;
    }

    let body: unknown;
    try {
        body = await response.clone().json();
    } catch {
        return undefined;
    }
    return isProblemDetails(body) ? createPlatformError(body, response.status) : undefined;
}

function isApiError(value: unknown): value is ApiError {
    return (
        value instanceof Error &&
        'responseStatusCode' in value &&
        (typeof value.responseStatusCode === 'number' || value.responseStatusCode === undefined)
    );
}

/**
 * Compatibility helper for callers that normalize thrown transport errors.
 * Raw Problem Details responses are converted by the adapter middleware before
 * Kiota deserializes them; unmapped Kiota errors fall back to status-based codes.
 */
export function parseHttpError(error: unknown): Promise<unknown> {
    if (error instanceof PlatformError) return Promise.resolve(error);
    if (!isApiError(error) || error.responseStatusCode === undefined) {
        return Promise.resolve(error);
    }

    const status = error.responseStatusCode;
    const code = statusToCode(status);
    const Ctor = CODE_TO_CLASS[code] ?? PlatformError;
    return Promise.resolve(
        new Ctor({
            code,
            status,
            detail: error.message || `HTTP ${status.toString()}`,
        }),
    );
}
