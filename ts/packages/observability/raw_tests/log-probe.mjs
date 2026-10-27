import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import {
    createLogger,
    outgoingHeaders,
    withIncomingContext,
    withUncorrelatedContext,
    parseRecord,
    validateRecord,
} from '@onenexus-team/observability';

const [command, file, expectedTrace, expectedService = 'typescript-package-probe'] =
    process.argv.slice(2);
if (command === 'emit') {
    const logger = createLogger({
        service: 'typescript-package-probe',
        environment: 'development',
        region: 'region-1',
        allowedFields: ['attempt'],
    });
    const metadata = withIncomingContext(
        [['traceparent', '00-11111111111111111111111111111111-2222222222222222-01']],
        { trusted: true },
        () => {
            assert(
                logger.log('Request accepted', { event: 'request.accepted', outcome: 'success' }),
            );
            return JSON.stringify(outgoingHeaders());
        },
    );
    for (const attempt of [1, 2]) {
        await withIncomingContext(
            Object.entries(JSON.parse(metadata)),
            { trusted: true },
            async () => {
                await Promise.resolve();
                assert(
                    logger.log('Work completed', {
                        event: 'work.completed',
                        outcome: 'success',
                        fields: { attempt },
                    }),
                );
            },
        );
    }
    withUncorrelatedContext(() => assert(logger.log('System ready')));
    assert(await logger.close());
    assert.equal(logger.stats().written, 4);
} else if (command === 'verify' && file && expectedTrace) {
    const rows = readFileSync(file, 'utf8').trim().split('\n').map(parseRecord);
    assert.equal(rows.length, 4, 'expected_four_records');
    for (const row of rows) {
        assert.deepEqual(validateRecord(row), [], 'invalid_common_fields');
        assert.equal(row.service, expectedService, 'wrong_service');
        assert.equal(row.environment, 'development', 'wrong_environment');
        assert.equal(row.region, 'region-1', 'wrong_region');
    }
    for (const row of rows.slice(0, 3)) assert.equal(row.trace_id, expectedTrace, 'wrong_trace');
    assert.equal(rows[0].event, 'request.accepted');
    assert.deepEqual(
        rows.slice(1, 3).map((r) => r.attempt),
        [1, 2],
    );
    assert.equal(rows[3].trace_id, undefined, 'system_context_leak');
    console.log('PASS: schema, trace, service, attempts, environment and system isolation');
} else {
    throw Error('usage: log-probe.mjs emit | verify file trace_id [service]');
}
