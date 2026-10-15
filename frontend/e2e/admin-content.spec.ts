import { expect, test } from '@playwright/test';

test('admin reads every item of a skill on a phone', async ({ page }) => {
	await page.setViewportSize({ width: 375, height: 800 });
	await page.goto('/admin');
	await page.getByLabel('Password').fill(process.env.E2E_ADMIN_PASSWORD as string);
	await page.getByRole('button', { name: 'Sign in' }).click();
	await page.getByRole('button', { name: 'Content' }).click();

	await expect(page.getByText(/version \d+\.\d+\.\d+/)).toBeVisible();
	await expect(page.getByText('live', { exact: true })).toBeVisible();
	await page.getByRole('button', { name: 'Preview Add to 20' }).click();

	const preview = page.getByRole('region', { name: 'Skill preview' });
	await expect(preview.getByRole('heading', { name: /Word problems \(15\)/ })).toBeVisible();
	await expect(preview.getByText(/^Answer:/).first()).toBeVisible();
	await expect(preview.getByRole('heading', { name: 'Hints (for seed 1)' })).toBeVisible();

	await preview.getByLabel('Seed (blank for samples)').fill('42');
	await preview.getByLabel('Tier').selectOption('2');
	await preview.getByRole('button', { name: 'Show' }).click();
	await expect(preview.getByText('Grade 1, keypad numpad, seeds 42')).toBeVisible();

	const overflow = await page.evaluate(
		() => document.documentElement.scrollWidth - document.documentElement.clientWidth
	);
	expect(overflow).toBeLessThanOrEqual(0);
});
