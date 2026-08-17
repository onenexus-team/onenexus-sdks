const REGION_LABEL = /^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$/;

interface Origin {
    readonly protocol: 'http:' | 'https:';
    readonly hostname: string;
    readonly port: string;
    readonly canonical: string;
}

/** Select the trusted CAS endpoint for AssumeS3Role from an access-token issuer. */
export function resolveAssumeS3RoleBaseUrl(globalBaseUrl: string, accessToken: string): string {
    const globalOrigin = parseOrigin(globalBaseUrl.replace(/\/$/, ''));
    if (globalOrigin === undefined || !globalOrigin.hostname.startsWith('auth.')) {
        throw new TypeError('CAS base URL must be the global auth.<domain> endpoint.');
    }

    const rootDomain = globalOrigin.hostname.slice('auth.'.length);
    if (rootDomain.length === 0) {
        throw new TypeError('CAS base URL must be the global auth.<domain> endpoint.');
    }

    const claims = parseJwtClaims(accessToken);
    if (claims === undefined) return globalOrigin.canonical;

    const issuer = claims.iss;
    const issuerOrigin = typeof issuer === 'string' ? parseOrigin(issuer) : undefined;
    if (issuerOrigin === undefined) {
        throw new TypeError('CAS access token contains an invalid issuer.');
    }

    if (sameOrigin(globalOrigin, issuerOrigin)) return issuerOrigin.canonical;

    if (issuerOrigin.hostname.startsWith('auth.')) {
        const issuerDomain = issuerOrigin.hostname.slice('auth.'.length);
        const parentSuffix = `.${issuerDomain}`;
        const possibleConfiguredRegion = rootDomain.endsWith(parentSuffix)
            ? rootDomain.slice(0, -parentSuffix.length)
            : '';
        if (REGION_LABEL.test(possibleConfiguredRegion)) {
            throw new TypeError('CAS base URL must be the global auth.<domain> endpoint.');
        }
    }

    const regionalSuffix = `.${rootDomain}`;
    const issuerWithoutAuth = issuerOrigin.hostname.startsWith('auth.')
        ? issuerOrigin.hostname.slice('auth.'.length)
        : issuerOrigin.hostname;
    const region = issuerWithoutAuth.endsWith(regionalSuffix)
        ? issuerWithoutAuth.slice(0, -regionalSuffix.length)
        : '';

    if (
        issuerOrigin.protocol !== globalOrigin.protocol ||
        issuerOrigin.port !== globalOrigin.port ||
        !issuerOrigin.hostname.startsWith('auth.') ||
        !issuerOrigin.hostname.endsWith(regionalSuffix) ||
        !REGION_LABEL.test(region)
    ) {
        throw new TypeError('CAS access token issuer is not trusted for regional routing.');
    }

    return issuerOrigin.canonical;
}

function parseJwtClaims(accessToken: string): Record<string, unknown> | undefined {
    const parts = accessToken.split('.');
    if (parts.length !== 3) return undefined;

    const payload = parts[1];
    if (payload === undefined) return undefined;

    const base64 = payload.replace(/-/g, '+').replace(/_/g, '/').padEnd(
        payload.length + ((4 - (payload.length % 4)) % 4),
        '=',
    );
    try {
        const binary = globalThis.atob(base64);
        const bytes = Uint8Array.from(binary, (character) => character.charCodeAt(0));
        const value: unknown = JSON.parse(new TextDecoder().decode(bytes));
        return value !== null && typeof value === 'object' && !Array.isArray(value)
            ? (value as Record<string, unknown>)
            : undefined;
    } catch {
        return undefined;
    }
}

function parseOrigin(value: string): Origin | undefined {
    let parsed: URL;
    try {
        parsed = new URL(value);
    } catch {
        return undefined;
    }

    if (
        (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') ||
        parsed.username !== '' ||
        parsed.password !== '' ||
        parsed.pathname !== '/' ||
        parsed.search !== '' ||
        parsed.hash !== ''
    ) {
        return undefined;
    }

    return {
        protocol: parsed.protocol,
        hostname: parsed.hostname.toLowerCase(),
        port: parsed.port,
        canonical: parsed.origin,
    };
}

function sameOrigin(left: Origin, right: Origin): boolean {
    return (
        left.protocol === right.protocol &&
        left.hostname === right.hostname &&
        left.port === right.port
    );
}
