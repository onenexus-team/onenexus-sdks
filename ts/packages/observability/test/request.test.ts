import { readFileSync } from 'node:fs';
import { Writable } from 'node:stream';
import { describe, expect, it } from 'vitest';
import {
    RequestLogContext,
    withIncomingContext,
    withRequestLogContext,
    currentRequestFields,
    createLogger,
    parseRecord,
    validateRecord,
} from '@onenexus-team/observability';

const tenant = '1'.repeat(32);
const owner = `nx1://test/${tenant}/CAS/global/User/${'2'.repeat(32)}`;
function logger() {
    const rows: Record<string, unknown>[] = [];
    const stream = new Writable({
        write(chunk: Buffer, _encoding, done) {
            rows.push(parseRecord(chunk.toString()) as Record<string, unknown>);
            done();
        },
    });
    return {
        rows,
        log: createLogger(
            { service: 'request-test', environment: 'development', region: 'test' },
            stream,
        ),
    };
}

describe('request contract', () => {
    it('emits shared scenarios and enriches application logs without fabricating traces', async () => {
        const suite = JSON.parse(
            readFileSync(
                process.env.ONENEXUS_LOGGING_SCENARIOS ?? '../../../tests/logging/scenarios.json',
                'utf8',
            ),
        ) as {
            request_emission_cases: {
                id: string;
                traceparent: string | null;
                principal: string | null;
                tenant: string | null;
                error: string | null;
                status: number | null;
                interrupted: boolean;
                expected: Record<string, unknown>;
            }[];
        };
        for (const c of suite.request_emission_cases) {
            const { rows, log } = logger();
            const receipt = new RequestLogContext();
            withIncomingContext(
                c.traceparent ? [['traceparent', c.traceparent]] : [],
                { trusted: true },
                () =>
                    withRequestLogContext(receipt, () => {
                        receipt.bindVerifiedIdentity(c.principal, c.tenant);
                        if (c.error) receipt.setError(c.error);
                        expect(
                            log.log('Application event', { fields: { principal_id: 'spoofed' } }),
                        ).toBe(true);
                        expect(
                            log.log('Request finished', {
                                fields: receipt.terminalFields(
                                    'POST',
                                    '/items/{id}',
                                    c.status,
                                    1.5,
                                    c.interrupted,
                                ),
                            }),
                        ).toBe(true);
                    }),
            );
            receipt.close();
            log.log('Outside request');
            expect(rows[0]!.principal_id).toBe(c.principal);
            expect(rows[1]).toMatchObject(c.expected);
            expect(validateRecord(rows[1], 'request')).toEqual([]);
            for (const row of rows) expect(row).not.toHaveProperty('request_id');
            if (c.traceparent === null) expect(rows[1]).not.toHaveProperty('trace_id');
            expect(rows[2]).not.toHaveProperty('principal_id');
            await log.close();
        }
    });

    it('enforces terminal fields at emission', async () => {
        const { rows, log } = logger();
        expect(log.log('Missing fields', { fields: { request_event: 'completed' } })).toBe(false);
        const r = new RequestLogContext();
        for (const [status, duration] of [
            [null, 1],
            [600, 1],
            [200, -1],
            [200, NaN],
        ] as const) {
            expect(
                log.log('Invalid request', {
                    fields: r.terminalFields('GET', '/', status, duration),
                }),
            ).toBe(false);
        }
        expect(rows).toEqual([]);
        expect(log.stats().invalid).toBe(5);
        r.close();
        await log.close();
    });

    it('validates attribution, resets nested contexts and prevents late rebinding', () => {
        const outer = new RequestLogContext();
        withRequestLogContext(outer, () => {
            outer.bindVerifiedIdentity(owner, tenant);
            const inner = new RequestLogContext();
            withRequestLogContext(inner, () =>
                expect(currentRequestFields().principal_id).toBeNull(),
            );
            inner.close();
            expect(currentRequestFields().principal_id).toBe(owner);
            for (const [p, t] of [
                [owner, '3'.repeat(32)],
                ['username', tenant],
                [owner, '0'.repeat(32)],
            ] as const) {
                outer.bindVerifiedIdentity(p, t);
                expect(outer.fields().principal_id).toBeNull();
            }
            expect(() => outer.setError('secret message')).toThrow('invalid_error_code');
        });
        outer.close();
        outer.bindVerifiedIdentity(owner, tenant);
        outer.setError('LATE');
        expect(outer.fields()).toEqual({});
        expect(currentRequestFields()).toEqual({});
        expect(() => outer.terminalFields('GET', '/', 200, 1)).toThrow('request_context_closed');
    });

    it('isolates concurrent requests and clears detached async work', async () => {
        await Promise.all(
            Array.from({ length: 20 }, async (_, i) => {
                const r = new RequestLogContext();
                try {
                    await withRequestLogContext(r, async () => {
                        const principal =
                            owner.slice(0, owner.lastIndexOf('/') + 1) +
                            (i + 1).toString(16).padStart(32, '0');
                        r.bindVerifiedIdentity(principal, tenant);
                        await Promise.resolve();
                        expect(currentRequestFields().principal_id).toBe(principal);
                    });
                } finally {
                    r.close();
                }
            }),
        );
        let resume!: () => void;
        const wait = new Promise<void>((resolve) => {
            resume = resolve;
        });
        const r = new RequestLogContext();
        const child = withRequestLogContext(r, async () => {
            r.bindVerifiedIdentity(owner, tenant);
            await wait;
            r.bindVerifiedIdentity(owner, tenant);
            return currentRequestFields();
        });
        r.close();
        resume();
        expect(await child).toEqual({});
        const failed = new RequestLogContext();
        try {
            await withRequestLogContext(failed, async () => {
                await Promise.resolve();
                throw Error('failure');
            });
        } catch {
            /* response middleware owns the error */
        } finally {
            failed.close();
        }
        expect(currentRequestFields()).toEqual({});
    });
});
