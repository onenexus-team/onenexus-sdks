import { describe, expect, it } from 'vitest';

import { resolveAssumeS3RoleBaseUrl } from '../src/routing.js';

function unsignedAccessToken(issuer: string): string {
    const encode = (value: object) => Buffer.from(JSON.stringify(value)).toString('base64url');
    return `${encode({ alg: 'ES256' })}.${encode({ iss: issuer })}.signature`;
}

describe('resolveAssumeS3RoleBaseUrl', () => {
    it('keeps global and opaque tokens on the configured global endpoint', () => {
        const globalBaseUrl = 'https://auth.onenexus.test';

        expect(resolveAssumeS3RoleBaseUrl(globalBaseUrl, 'opaque-token')).toBe(globalBaseUrl);
        expect(
            resolveAssumeS3RoleBaseUrl(
                globalBaseUrl,
                unsignedAccessToken('https://auth.onenexus.test'),
            ),
        ).toBe(globalBaseUrl);
    });

    it('routes a regional token to its same-domain issuer', () => {
        expect(
            resolveAssumeS3RoleBaseUrl(
                'https://auth.onenexus.test',
                unsignedAccessToken('https://auth.ric1.onenexus.test'),
            ),
        ).toBe('https://auth.ric1.onenexus.test');
    });

    it('requires the configured URL to be the global auth endpoint', () => {
        expect(() => resolveAssumeS3RoleBaseUrl('https://cas.onenexus.test', 'opaque')).toThrow(
            /global auth\.<domain> endpoint/,
        );
        expect(() =>
            resolveAssumeS3RoleBaseUrl(
                'https://auth.ric1.onenexus.test',
                unsignedAccessToken('https://auth.onenexus.test'),
            ),
        ).toThrow(/global auth\.<domain> endpoint/);
    });

    it('rejects issuers outside the configured root domain', () => {
        expect(() =>
            resolveAssumeS3RoleBaseUrl(
                'https://auth.onenexus.test',
                unsignedAccessToken('https://auth.ric1.attacker.test'),
            ),
        ).toThrow(/not trusted/);
    });
});
