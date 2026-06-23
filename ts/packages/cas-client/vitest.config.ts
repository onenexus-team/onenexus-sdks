import { defineConfig } from 'vitest/config';

export default defineConfig({
    // `customConditions: ["development"]` in tsconfig.base.json is honoured by
    // TypeScript at compile time. Vitest runs through Vite, which does its own
    // resolution and would otherwise pick the `import` condition → `dist/`
    // (not built yet during tests). Listing `development` first here mirrors
    // tsc's behaviour so cas-client tests resolve sibling workspace packages
    // (notably `@onenexus-team/sdk-core`) directly from source.
    resolve: {
        conditions: ['development', 'import', 'module', 'node', 'default'],
    },
    test: {
        include: ['test/**/*.test.ts'],
        environment: 'node',
        coverage: {
            provider: 'v8',
            include: ['src/**/*.ts'],
            exclude: ['src/generated/**', 'src/**/index.ts', 'src/mutator.ts'],
            reporter: ['text', 'html'],
        },
    },
});
