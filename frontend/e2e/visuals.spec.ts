import { expect, test, type Page } from '@playwright/test';
import { SAMPLE_VISUALS } from '../src/shared/visuals/samples';

/**
 * Every lesson visual, drawn in a real browser at phone widths: a lesson with one screen
 * per visual is served in place of the real one, and each picture must fit the screen
 * with no horizontal scroll.
 */

const CSRF = { 'X-Requested-With': 'mathquest' };
const SHOT_DIR = process.env.E2E_SHOT_DIR;

const LESSON = {
	skill_id: 'add_within_10',
	skill_name: 'Add to 10',
	screens: SAMPLE_VISUALS.map((visual) => ({
		title: visual.kind,
		body: [{ kind: 'text', value: `This screen shows a ${visual.kind.replace('_', ' ')}.` }],
		visual
	})),
	worked_example: { prompt: [{ kind: 'math', value: '1 + 1 = ?' }], steps: [[{ kind: 'text', value: 'Two.' }]] },
	try_it: { tier: 0 }
};

async function signUp(page: Page) {
	const suggestion = await page.request.get('/api/auth/nickname-suggestion');
	const { nickname } = (await suggestion.json()) as { nickname: string };
	const signup = await page.request.post('/api/auth/signup', {
		headers: CSRF,
		data: { signup_word: process.env.E2E_SIGNUP_WORD ?? '', nickname, pin: '1234' }
	});
	expect(signup.ok()).toBe(true);
}

test('every visual and the try-it card fit a 320 px and a 375 px screen', async ({ page }) => {
	await signUp(page);
	await page.route('**/api/play/sessions/*/next', (route) =>
		route.fulfill({ json: { type: 'lesson', skill_id: LESSON.skill_id, skill_name: LESSON.skill_name } })
	);
	await page.route(`**/api/lessons/${LESSON.skill_id}`, (route) => route.fulfill({ json: LESSON }));

	for (const width of [320, 375]) {
		await test.step(`${width} px`, async () => {
			await page.setViewportSize({ width, height: 740 });
			await page.goto('/play');
			const lesson = page.getByTestId('lesson');
			await expect(lesson).toBeVisible();
			for (const visual of SAMPLE_VISUALS) {
				const svg = lesson.locator(`svg[data-visual="${visual.kind}"]`);
				await expect(svg).toBeVisible();
				await expect(svg).toHaveAttribute('role', 'img');
				expect((await svg.getAttribute('aria-label'))?.length ?? 0).toBeGreaterThan(10);
				const m = await svg.evaluate((el) => {
					const r = el.getBoundingClientRect();
					const doc = document.documentElement;
					return {
						left: r.left,
						right: r.right,
						height: r.height,
						scroll: doc.scrollWidth,
						client: doc.clientWidth
					};
				});
				expect(m.left, `${visual.kind} left edge`).toBeGreaterThanOrEqual(0);
				expect(m.right, `${visual.kind} right edge`).toBeLessThanOrEqual(width);
				expect(m.height, `${visual.kind} height`).toBeGreaterThan(20);
				expect(m.scroll, `${visual.kind} horizontal scroll`).toBeLessThanOrEqual(m.client);
				if (SHOT_DIR) await page.screenshot({ path: `${SHOT_DIR}/visual-${visual.kind}-${width}.png` });
				await lesson.getByRole('button', { name: 'Next', exact: true }).click();
			}
			// Worked example, then the try-it card inside the lesson: still no sideways scroll.
			await lesson.getByRole('button', { name: 'Next', exact: true }).click();
			await expect(page.getByTestId('lesson-try').getByTestId('math-field')).toBeVisible();
			const doc = await page.evaluate(() => ({
				scroll: document.documentElement.scrollWidth,
				client: document.documentElement.clientWidth
			}));
			expect(doc.scroll, 'try-it horizontal scroll').toBeLessThanOrEqual(doc.client);
			if (SHOT_DIR) await page.screenshot({ path: `${SHOT_DIR}/lesson-try-${width}.png`, fullPage: true });
		});
	}
});
