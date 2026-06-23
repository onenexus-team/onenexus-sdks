/**
 * `@onenexus/sdk-core` — credential primitives and HTTP transport shared by
 * every service-specific SDK package.
 *
 * The credential object system is documented in the repository `README.md`.
 * Server-side concerns (token validation, codegen internals, per-service SDK
 * shape) are out of scope.
 */

export * from './credentials/index.js';
export * from './http/index.js';
export * from './client-base.js';
