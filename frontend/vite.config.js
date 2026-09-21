import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
export default defineConfig({
    base: process.env.GITHUB_PAGES === 'true' ? '/hr-agent/' : '/',
    build: { target: 'es2019' },
    plugins: [react()],
});
