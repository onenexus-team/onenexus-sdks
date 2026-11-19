import { AsyncLocalStorage } from 'node:async_hooks';
import type { LogFields } from './logging.js';

export const REQUEST_FIELDS: readonly string[] = Object.freeze([
    'principal_id',
    'tenant_id',
    'error_code',
    'request_event',
    'http.request.method',
    'http.route',
    'http.response.status_code',
    'duration_ms',
]);
const errorCode = /^[A-Za-z0-9._:-]{1,128}$(?![\s\S])/;
const tenant = /^[0-9a-f]{32}$(?![\s\S])/;
const principal =
    /^nx1:\/\/[A-Za-z0-9._:-]+\/([0-9a-f]{32})\/[A-Za-z0-9._:-]+\/[A-Za-z0-9._:-]+\/(User|ServiceClient|Workload)\/[A-Za-z0-9._:-]+$(?![\s\S])/;
const requests = new AsyncLocalStorage<RequestLogContext>();

/** Attribution only. Callers own authentication, policy and response observation. */
export class RequestLogContext {
    private values: Record<string, string | null> = { principal_id: null, tenant_id: null };
    private closed = false;

    /** Call only after credential verification, before policy/quota checks. */
    bindVerifiedIdentity(principalId: string | null, tenantId: string | null): void {
        const verifiedTenant =
            typeof tenantId === 'string' && tenant.test(tenantId) && tenantId !== '0'.repeat(32)
                ? tenantId
                : null;
        const match =
            typeof principalId === 'string' && principalId.length <= 1024
                ? principal.exec(principalId)
                : null;
        if (this.closed) return;
        this.values.tenant_id = verifiedTenant;
        this.values.principal_id =
            match && verifiedTenant && match[1] === verifiedTenant ? principalId : null;
    }

    setError(code: string): void {
        if (typeof code !== 'string' || !errorCode.test(code)) throw Error('invalid_error_code');
        if (!this.closed) this.values.error_code = code;
    }

    fields(): LogFields {
        return { ...this.values };
    }

    terminalFields(
        method: string,
        route: string,
        statusCode: number | null,
        durationMs: number,
        interrupted = false,
    ): LogFields {
        if (this.closed) throw Error('request_context_closed');
        return {
            ...this.values,
            request_event: interrupted ? 'interrupted' : 'completed',
            'http.request.method': method,
            'http.route': route,
            'http.response.status_code': statusCode,
            duration_ms: durationMs,
            error_code:
                this.values.error_code ??
                (statusCode !== null && statusCode >= 400 ? 'UNCLASSIFIED' : null),
        };
    }

    /** Call from the HTTP finish/close fence, including health and error paths. */
    close(): void {
        this.closed = true;
        this.values = {};
    }
}

/** Does not close automatically: callback middleware often returns before the response finishes. */
export function withRequestLogContext<T>(receipt: RequestLogContext, work: () => T): T {
    return requests.run(receipt, work);
}

export function currentRequestFields(): LogFields {
    return requests.getStore()?.fields() ?? {};
}
