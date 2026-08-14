/**
 * `@onenexus-team/cas-client` — typed client for the Central Auth Service.
 *
 * Generated from `specs/cas/openapi.json` via Kiota; consumed through the
 * hand-written flat {@link CasClient} facade backed by a core-owned request
 * adapter.
 *
 * Credential primitives, Kiota adapter construction, and the typed
 * error hierarchy (`PlatformError` and subclasses) live in
 * `@onenexus-team/sdk-core`. Import from there directly when you need them.
 */

export { CasClient, type CasClientConfig, type CasRequestOptions } from './client.js';

// Re-export the generated request/response schemas as types. Consumers
// typically import these to declare local variables typed against the
// CAS contract (e.g. `const req: CreateTenantRequest = { ... }`).
export type * from './generated/models/index.js';
