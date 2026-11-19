import { defineConfig } from 'vitest/config';
export default defineConfig({
    resolve: { conditions: ['development', 'import', 'module', 'node', 'default'] },
    test: { include: ['test/**/*.test.ts'], environment: 'node' },
});
