import { defineConfig } from 'orval';

/**
 * Orval configuration for `@onenexus-team/cas-support-client`.
 *
 * Mirrors `@onenexus-team/cas-client`'s setup — the only differences are the input
 * spec and the generated output filename. See cas-client's `orval.config.ts`
 * for the full rationale behind each option.
 *
 * - `input.target` points at the OpenAPI spec under `specs/cas-support/`.
 *   Path is resolved relative to this config file. This is the Support API
 *   (`/support-api/*`), a distinct surface from the regular CAS `/api/*` RPCs.
 * - `mode: 'tags-split'` produces one generated module per OpenAPI tag
 *   (currently just `Tenant`) under `src/generated/`.
 * - `client: 'axios'` selects the axios-shaped generator whose calls invoke
 *   the mutator as `mutator(config, options)`; `CasSupportClient` binds the
 *   per-call `{ http: KyInstance }` option once per group.
 * - `mutator.path` is service-local and re-exports `platformMutator` from
 *   `@onenexus-team/sdk-core`.
 */
export default defineConfig({
    'cas-support': {
        input: {
            target: '../../../specs/cas-support/openapi.json',
        },
        output: {
            mode: 'tags-split',
            target: './src/generated/cas-support.ts',
            schemas: './src/generated/schemas',
            client: 'axios',
            baseUrl: '',
            override: {
                mutator: {
                    path: './src/mutator.ts',
                    name: 'platformMutator',
                },
            },
        },
    },
});
