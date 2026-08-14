/**
 * `@onenexus-team/cas-support-client` — typed client for the Central Auth Service
 * Support API (`/support-api/*`).
 *
 * Generated from `specs/cas-support/openapi.json` via Kiota; consumed through
 * the hand-written flat {@link CasSupportClient} facade backed by a core-owned
 * request adapter.
 *
 * This is a distinct API surface from `@onenexus-team/cas-client` (the regular CAS
 * `/api/*` RPCs). Credential primitives, Kiota adapter construction, and
 * the typed error hierarchy (`PlatformError` and subclasses) live in
 * `@onenexus-team/sdk-core`. Import from there directly when you need them.
 */

export {
    CasSupportClient,
    type CasSupportClientConfig,
    type CasSupportRequestOptions,
} from './client.js';

// Re-export the generated request/response schemas as types. Consumers
// typically import these to declare local variables typed against the
// CAS Support contract (e.g. `const req: CreateTenantRequest = { ... }`).
export type * from './generated/models/index.js';
