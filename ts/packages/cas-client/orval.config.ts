import { defineConfig } from 'orval';

/**
 * Orval configuration for `@onenexus/cas-client`.
 *
 * - `input.target` points at the OpenAPI spec under `specs/cas/`.
 *   Path is resolved relative to this config file.
 * - `mode: 'tags-split'` produces one generated module per OpenAPI tag
 *   (TenantUser, …) under `src/generated/`.
 * - `baseUrl: ''` keeps URLs path-relative; the runtime base URL is
 *   supplied by `CasClient` via Ky's `prefixUrl` inside the mutator.
 * - `client: 'axios'` picks the axios-shaped generator: every generated
 *   call invokes the mutator as `mutator(config, options)` where `config`
 *   is `{ url, method, data, headers, params, signal, ... }` and `options`
 *   is the per-call `SecondParameter` slot we use to thread the consumer's
 *   Ky instance through as `{ http: KyInstance }`. The `CasClient` grouped
 *   API adapters bind that option once per group, so consumers never pass it.
 * - The `mutator.path` is service-local; it points at `./src/mutator.ts`
 *   which re-exports `platformMutator` from `@onenexus/sdk-core`. orval
 *   bakes that path into the generated `import` statements.
 */
export default defineConfig({
    cas: {
        input: {
            target: '../../../specs/cas/openapi.json',
        },
        output: {
            mode: 'tags-split',
            target: './src/generated/cas.ts',
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
