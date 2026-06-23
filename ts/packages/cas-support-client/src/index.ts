/**
 * `@onenexus-team/cas-support-client` — typed client for the Central Auth Service
 * Support API (`/support-api/*`).
 *
 * Generated from `specs/cas-support/openapi.json` via orval; consumed via
 * the hand-written {@link CasSupportClient} class which extends `ClientBase`
 * and threads its transport through to the orval-generated functions on every
 * call.
 *
 * This is a distinct API surface from `@onenexus-team/cas-client` (the regular CAS
 * `/api/*` RPCs). Credential primitives, the HTTP transport (`createKy`), and
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
export type * from './generated/schemas/index.js';
