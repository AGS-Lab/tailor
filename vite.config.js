import { defineConfig } from 'vite'

export default defineConfig({
    clearScreen: false,
    server: {
        port: 5173,
        strictPort: true,
        watch: {
            ignored: ['**/src-tauri/target/**', '**/src-tauri/gen/**', '**/node_modules/**', '**/.git/**'],
        },
    },
    envPrefix: ['VITE_', 'TAURI_'],
    build: {
        target: ['es2021', 'chrome100', 'safari13'],
        minify: !process.env.TAURI_DEBUG ? 'esbuild' : false,
        sourcemap: !!process.env.TAURI_DEBUG,
    },
})
