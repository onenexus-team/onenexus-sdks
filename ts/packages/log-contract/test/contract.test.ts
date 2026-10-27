import { describe, expect, it } from 'vitest';
import {
    CONTRACT_DIGEST,
    CONTRACT_VERSION,
    ContractViolation,
    encodeRecord,
    loadContract,
    parseRecord,
    validateRecord,
} from '@onenexus-team/log-contract';

const valid = {
    timestamp: 1792573200000000000n,
    level: 'INFO',
    service: 'test',
    environment: 'development',
    region: 'ric1',
    message: 'Safe message',
};

describe('canonical contract', () => {
    const data = loadContract();
    for (const item of data.vectors.record_cases) {
        it(item.id, () => expect(validateRecord(item.record, item.profile)).toEqual(item.errors));
    }
    it('exposes version and digest without mutable internal schema', () => {
        expect(CONTRACT_VERSION).toBe(data.manifest.version);
        expect(CONTRACT_DIGEST).toMatch(/^[0-9a-f]{64}$/);
        data.schema.$defs.common.required = [];
        expect(validateRecord({})).toContain('missing_or_invalid_message');
        expect(loadContract().schema.$defs.common.required).toContain('message');
    });
    it('preserves exact int64 timestamp boundaries', () => {
        expect(encodeRecord(valid)).toContain('1792573200000000000');
        expect(parseRecord(encodeRecord(valid))).toEqual(valid);
        expect(validateRecord({ ...valid, timestamp: 9223372036854775807n })).toEqual([]);
        expect(validateRecord({ ...valid, timestamp: 9223372036854775808n })).toContain(
            'schema_invalid',
        );
        expect(validateRecord({ ...valid, timestamp: -1n })).toContain('schema_invalid');
        expect(validateRecord({ ...valid, timestamp: 0.5 })).toContain('schema_invalid');
        expect(validateRecord({ ...valid, timestamp: true })).toContain('schema_invalid');
        expect(validateRecord({ ...valid, timestamp: Number(valid.timestamp) })).toContain(
            'schema_invalid',
        );
    });
    it('rejects unknown profiles and returns only stable error codes', () => {
        expect(validateRecord(valid, 'unknown')).toEqual(['unknown_profile']);
        expect(validateRecord(null)).toEqual(['schema_invalid']);
        expect(() => encodeRecord({ ...valid, message: '' })).toThrow(ContractViolation);
        expect(() => encodeRecord({ ...valid, message: '' })).toThrow('missing_or_invalid_message');
    });
    it('rejects unsafe serialization without executing getters or toJSON', () => {
        const fail = () => {
            throw new Error('must_not_run');
        };
        for (const extension of [
            NaN,
            Infinity,
            1n,
            undefined,
            new Date(),
            () => 1,
            { toJSON: fail },
        ]) {
            expect(validateRecord({ ...valid, extension })).toContain('invalid_json_record');
        }
        const getter = Object.defineProperty({}, 'secret', { get: fail, enumerable: true });
        expect(validateRecord({ ...valid, extension: getter })).toEqual(['invalid_json_record']);
        let getterCalled = false;
        const array = Object.defineProperty([], '0', {
            get() {
                getterCalled = true;
                return 1;
            },
        });
        expect(validateRecord({ ...valid, extension: array })).toEqual(['invalid_json_record']);
        expect(getterCalled).toBe(false);
        const cycle: Record<string, unknown> = {};
        cycle.self = cycle;
        expect(validateRecord({ ...valid, extension: cycle })).toEqual(['invalid_json_record']);
        expect(validateRecord({ ...valid, message: '\ud800' })).toContain('invalid_json_record');
        expect(encodeRecord({ ...valid, extension: [1, true, null, 'Unicode ✓'] })).toContain(
            'Unicode ✓',
        );
    });
});
