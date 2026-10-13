import adapter from '@sveltejs/adapter-static';
import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vitest/config';

const apiTarget = 'http://127.0.0.1:8000';

export default defineConfig({
	plugins: [
		sveltekit({
			compilerOptions: {
				// Force runes mode for the project, except for libraries.
				runes: ({ filename }) =>
					filename.split(/[/\\]/).includes('node_modules') ? undefined : true
			},
			adapter: adapter({ fallback: 'index.html' })
		})
	],
	server: { proxy: { '/api': apiTarget } },
	preview: { proxy: { '/api': apiTarget } },
	test: {
		include: ['src/**/*.test.ts']
	}
});
