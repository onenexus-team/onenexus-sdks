import { defineConfig } from 'tsup';

export default defineConfig({
    entry: {
        index: 'src/index.ts',
        'node/index': 'src/node/index.ts',
    },
    outDir: 'dist',
    format: ['esm'],
    target: 'es2022',
    dts: true,
    clean: true,
    sourcemap: true,
    treeshake: true,
    splitting: false,
});
