import { expect, test, type Page } from '@playwright/test';

async function signIn(page: Page) {
	await page.goto('/admin');
	await page.getByLabel('Password').fill(process.env.E2E_ADMIN_PASSWORD as string);
	await page.getByRole('button', { name: 'Sign in' }).click();
	await page.getByRole('button', { name: 'Content' }).click();
	await expect(page.getByText(/version \d+\.\d+\.\d+/)).toBeVisible();
}

/** Page overflow, and buttons shorter than a 44 px tap target. */
async function layout(page: Page) {
	return page.evaluate(() => ({
		overflow: document.documentElement.scrollWidth - window.innerWidth,
		small: [...document.querySelectorAll('.admin button, .admin input, .admin select')]
			.map((el) => el.getBoundingClientRect())
			.filter((r) => r.height > 0 && r.height < 44).length
	}));
}

test('admin reads every item of a skill on a phone', async ({ page }) => {
	await page.setViewportSize({ width: 375, height: 800 });
	await signIn(page);
	await expect(page.getByText('live', { exact: true })).toBeVisible();
	await page.getByRole('button', { name: 'Preview Add to 20' }).click();

	const preview = page.getByRole('region', { name: 'Skill preview' });
	await expect(preview.getByRole('heading', { name: /Word problems \(15\)/ })).toBeVisible();
	await expect(preview.getByText(/^Answer:/).first()).toBeVisible();
	await expect(preview.getByRole('heading', { name: 'Hints (for seed 1)' })).toBeVisible();

	await preview.getByLabel('Seed (blank for samples)').fill('9007199254740991');
	await preview.getByLabel('Tier').selectOption('2');
	await preview.getByRole('button', { name: 'Show' }).click();
	await expect(preview.getByText('Grade 1, keypad numpad, seeds 9007199254740991')).toBeVisible();
});

test('admin previews fit 320 and 375 px with 44 px taps', async ({ page }) => {
	// One sign-in for every case: admin logins are rate limited.
	await page.setViewportSize({ width: 375, height: 800 });
	await signIn(page);
	for (const width of [320, 375]) {
		for (const name of ['Add to 20', 'Add Fractions']) {
			await page.setViewportSize({ width, height: 800 });
			expect(await layout(page), `${width} overview`).toEqual({ overflow: 0, small: 0 });
			await page.getByRole('button', { name: `Preview ${name}` }).click();
			const preview = page.getByRole('region', { name: 'Skill preview' });
			await expect(
				preview.getByRole('heading', { level: 2, name: new RegExp(name) })
			).toBeVisible();
			expect(await layout(page), `${width} ${name}`).toEqual({ overflow: 0, small: 0 });
		}
	}
});
