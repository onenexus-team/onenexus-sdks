import { defineConfig } from 'tsup';

export default defineConfig({
    entry: { index: 'src/index.ts' },
    outDir: 'dist',
    format: ['esm'],
    target: 'es2022',
    dts: true,
    clean: true,
    sourcemap: true,
    treeshake: true,
    splitting: false,
    // Workspace peer. Don't bundle it into cas-client's dist — consumers
    // install `@onenexus/sdk-core` separately so credential primitives and
    // the mutator code live in exactly one place at runtime.
    external: ['@onenexus/sdk-core'],
});
