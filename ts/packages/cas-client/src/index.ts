/**
 * `@onenexus/cas-client` — typed client for the Central Auth Service.
 *
 * Generated from `specs/cas/openapi.json` via orval; consumed via the
 * hand-written {@link CasClient} class which extends `ClientBase` and threads
 * its transport through to the orval-generated functions on every call.
 *
 * Credential primitives, the HTTP transport (`createKy`), and the typed
 * error hierarchy (`PlatformError` and subclasses) live in
 * `@onenexus/sdk-core`. Import from there directly when you need them.
 */

export { CasClient, type CasClientConfig, type CasRequestOptions } from './client.js';

// Re-export the generated request/response schemas as types. Consumers
// typically import these to declare local variables typed against the
// CAS contract (e.g. `const req: CreateTenantRequest = { ... }`).
export type * from './generated/schemas/index.js';
