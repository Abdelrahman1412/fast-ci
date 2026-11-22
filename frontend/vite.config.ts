import { defineConfig } from 'vite';

const api = process.env.DEMO_API_URL ?? 'http://127.0.0.1:4010';

export default defineConfig({
  build: { outDir: 'dist', sourcemap: true },
  server: { proxy: { '/api': api } },
  preview: { proxy: { '/api': api } },
});
