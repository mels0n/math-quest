import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { expect, test, type Page } from '@playwright/test';

/**
 * Taps each keypad profile's sample key sequences and checks the LaTeX the answer
 * field ends up with. The same samples are parsed by the backend checker's tests, so
 * every key sequence here is one the checker reads.
 */

interface Sample {
	keys: string[];
	latex: string;
}

const SAMPLES = (
	JSON.parse(
		readFileSync(
			resolve(dirname(fileURLToPath(import.meta.url)), '../../testdata/keypad-samples.json'),
			'utf8'
		)
	) as { profiles: Record<string, Sample[]> }
).profiles;

const CSRF = { 'X-Requested-With': 'mathquest' };

async function signUp(page: Page) {
	const suggestion = await page.request.get('/api/auth/nickname-suggestion');
	const { nickname } = (await suggestion.json()) as { nickname: string };
	const signup = await page.request.post('/api/auth/signup', {
		headers: CSRF,
		data: { signup_word: process.env.E2E_SIGNUP_WORD ?? '', nickname, pin: '1234' }
	});
	expect(signup.ok()).toBe(true);
}

/** Serves every issued problem with the given keypad profile. */
async function serveKeypad(page: Page, keypad: string) {
	await page.unroute('**/api/play/sessions/*/next');
	await page.route('**/api/play/sessions/*/next', async (route) => {
		const response = await route.fetch();
		const body = (await response.json()) as Record<string, unknown>;
		await route.fulfill({ response, json: { ...body, keypad } });
	});
}

async function fieldValue(page: Page): Promise<string> {
	return page
		.getByTestId('math-field')
		.evaluate((el) => (el as unknown as { value: string }).value);
}

// One player for every profile: sign-ups are rate limited per client.
test('each keypad profile types the LaTeX the checker reads', async ({ page }) => {
	await signUp(page);
	await page.setViewportSize({ width: 375, height: 812 });
	for (const [profile, samples] of Object.entries(SAMPLES)) {
		await test.step(profile, async () => {
			await serveKeypad(page, profile);
			await page.goto('/play');
			await expect(page.getByTestId('math-field')).toBeVisible();
			const pad = page.getByRole('group', { name: 'Answer keypad' });

			if (samples.length === 0) {
				await expect(pad).toHaveCount(0);
				await expect(page.getByRole('button', { name: 'Go', exact: true })).toHaveCount(0);
				return;
			}
			await expect(pad).toHaveAttribute('data-profile', profile);
			for (const sample of samples) {
				await page.getByTestId('math-field').evaluate((el) => {
					(el as unknown as { value: string }).value = '';
				});
				for (const key of sample.keys) {
					await pad.getByRole('button', { name: key, exact: true }).click();
				}
				expect(await fieldValue(page), `${profile}: ${sample.keys.join(' ')}`).toBe(sample.latex);
			}
			const width = await page.evaluate(() => document.documentElement.scrollWidth);
			expect(width, `${profile}: page scroll width`).toBeLessThanOrEqual(375);
		});
	}
});
