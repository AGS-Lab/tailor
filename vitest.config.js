import { defineConfig } from 'vitest/config';

export default defineConfig({
    test: {
        environment: 'jsdom',
        globals: true, // Optional: if you want to use global text/expect without importing
    },
});
