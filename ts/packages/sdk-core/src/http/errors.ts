/**
 * RFC 9457 Problem Details (https://www.rfc-editor.org/rfc/rfc9457.html)
 * mapping for OneNexus platform RPC errors.
 *
 * The `code` extension is the canonical classifier; HTTP status is derived
 * from it. Both are always present and consistent.
 */

import { HTTPError } from 'ky';

/**
 * Initialiser for {@link PlatformError}. Mirrors the RFC 9457 member names
 * plus the platform-specific `code`, `requestId`, and `fieldErrors`
 * extensions.
 */
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

/**
 * Base class for every platform RPC error. Subclassed per `code` value so
 * consumers can branch on `instanceof InvalidArgumentError` etc.
 *
 * The constructor sets `name` from `new.target` so subclass instances stamp
 * the correct class name without each subclass having to set it manually.
 */
export class PlatformError extends Error {
    readonly code: string;
    readonly status: number;
    readonly detail: string;
    /** Mapped from RFC 9457 `type` — renamed to avoid clashing with `Error.type`. */
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

/** `code = "invalid_argument"` (HTTP 400). `fieldErrors` carries per-field details. */
export class InvalidArgumentError extends PlatformError {}
/** `code = "unauthenticated"` (HTTP 401). */
export class UnauthenticatedError extends PlatformError {}
/** `code = "forbidden"` (HTTP 403). */
export class ForbiddenError extends PlatformError {}
/** `code = "not_found"` (HTTP 404). */
export class NotFoundError extends PlatformError {}
/** `code = "already_exists"` (HTTP 409). */
export class AlreadyExistsError extends PlatformError {}
/** `code = "failed_precondition"` (HTTP 409). */
export class FailedPreconditionError extends PlatformError {}
/** `code = "resource_exhausted"` (HTTP 429). */
export class ResourceExhaustedError extends PlatformError {}
/** `code = "unavailable"` (HTTP 503). */
export class UnavailableError extends PlatformError {}
/** `code = "internal"` (HTTP 500). Catch-all server failure. */
export class InternalError extends PlatformError {}

/** Code → subclass constructor lookup. */
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

/** HTTP status → fallback code when the body has no `code` extension. */
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
    readonly type?: string;
    readonly title?: string;
    readonly status?: number;
    readonly detail?: string;
    readonly instance?: string;
    readonly code?: string;
    readonly requestId?: string;
    readonly errors?: Record<string, string[]>;
}

function isObject(value: unknown): value is Record<string, unknown> {
    return typeof value === 'object' && value !== null;
}

function isProblemDetails(value: unknown): value is ProblemDetailsBody {
    // Per RFC 9457, the minimum we need to recognise a Problem Details body is
    // an object. All members are optional in the spec. We additionally require
    // at least one of `code`, `title`, or `detail` to avoid mis-identifying
    // empty `{}` bodies as Problem Details.
    if (!isObject(value)) return false;
    return 'code' in value || 'title' in value || 'detail' in value || 'type' in value;
}

/**
 * Convert an unknown thrown value into a typed {@link PlatformError} where
 * possible.
 *
 * - Ky's `HTTPError` whose response body is `application/problem+json` (or
 *   plain `application/json` with a Problem-Details-shaped body) is parsed
 *   and rethrown as the matching subclass.
 * - Anything else (network errors, abort errors, non-JSON 5xx bodies) is
 *   returned unchanged so the caller can handle it directly.
 *
 * Returns the error rather than throwing so the caller controls the throw
 * site — typically a single `throw await parseHttpError(error)` line inside
 * a mutator's `catch`.
 */
export async function parseHttpError(error: unknown): Promise<unknown> {
    if (!(error instanceof HTTPError)) return error;

    const response = error.response;
    const contentType = response.headers.get('content-type') ?? '';
    const isProblemJson =
        contentType.includes('application/problem+json') ||
        contentType.includes('application/json');

    if (!isProblemJson) return error;

    let body: unknown;
    try {
        body = await response.clone().json();
    } catch {
        return error;
    }

    if (!isProblemDetails(body)) return error;

    const code = body.code ?? statusToCode(response.status);
    const Ctor = CODE_TO_CLASS[code] ?? PlatformError;

    const init: PlatformErrorInit = {
        code,
        status: body.status ?? response.status,
        detail: body.detail ?? body.title ?? `HTTP ${response.status.toString()}`,
        type: body.type,
        title: body.title,
        instance: body.instance,
        requestId: body.requestId,
        fieldErrors: body.errors,
    };
    return new Ctor(init);
}
