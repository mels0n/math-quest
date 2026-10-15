import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
	testDir: 'e2e',
	testMatch: '**/*.spec.ts',
	workers: 1,
	// On CI, failures also become check annotations so they are readable without the log.
	reporter: process.env.CI ? [['github'], ['list']] : 'list',
	timeout: 60_000,
	globalSetup: './e2e/global-setup.ts',
	use: {
		baseURL: 'http://127.0.0.1:4173',
		headless: true,
		viewport: { width: 900, height: 1000 }
	},
	projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'], headless: true } }],
	webServer: {
		command: 'npm run build && npm run preview -- --host 127.0.0.1 --port 4173 --strictPort',
		url: 'http://127.0.0.1:4173',
		timeout: 180_000,
		reuseExistingServer: false
	}
});
