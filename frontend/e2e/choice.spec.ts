import { expect, test, type Page, type Route } from '@playwright/test';
import { fetchProblem } from './problems';

/**
 * Multiple-choice problems: answer buttons instead of a keypad. The real backend issues
 * each problem and the browser test swaps in choices; answers are answered here, so the
 * test sees exactly what the page sends.
 */

interface PromptPart {
	kind: 'text' | 'math';
	value: string;
}

const CSRF = { 'X-Requested-With': 'mathquest' };
const SHOT_DIR = process.env.E2E_SHOT_DIR;
const PROMPT: PromptPart[] = [{ kind: 'text', value: 'Which fraction is the same as one half?' }];
const CHOICES: PromptPart[][] = [
	[{ kind: 'math', value: String.raw`\frac{2}{4}` }],
	[{ kind: 'math', value: String.raw`\frac{1}{3}` }],
	[{ kind: 'text', value: 'two thirds of a pie' }],
	[{ kind: 'math', value: String.raw`\frac{3}{8}` }]
];
const RIGHT = 0;

async function signUp(page: Page) {
	const suggestion = await page.request.get('/api/auth/nickname-suggestion');
	const { nickname } = (await suggestion.json()) as { nickname: string };
	const signup = await page.request.post('/api/auth/signup', {
		headers: CSRF,
		data: { signup_word: process.env.E2E_SIGNUP_WORD ?? '', nickname, pin: '1234' }
	});
	expect(signup.ok()).toBe(true);
}

async function serveChoices(page: Page) {
	await page.unroute('**/api/play/sessions/*/next');
	await page.route('**/api/play/sessions/*/next', async (route) => {
		const { response, body } = await fetchProblem(page, route);
		await route.fulfill({
			response,
			json: { ...body, prompt: PROMPT, keypad: 'choice', choices: CHOICES }
		});
	});
}

function result(verdict: string, attemptsLeft: number, answerChoice: number | null = null) {
	return {
		verdict,
		misconception: null,
		solved: verdict === 'correct',
		attempts_left: attemptsLeft,
		mastery: { skill_id: 'pick', state: 'learning', progress: 0.2 },
		answer_latex: null,
		answer_choice: answerChoice,
		total_solved: verdict === 'correct' ? 1 : 0
	};
}

/** Answers each submission from `replies` in turn and records the bodies sent. */
async function answerWith(page: Page, replies: object[], sent: unknown[]) {
	await page.unroute('**/api/play/problems/*/answer');
	await page.route('**/api/play/problems/*/answer', async (route: Route) => {
		sent.push(route.request().postDataJSON());
		await route.fulfill({ json: replies.shift() });
	});
}

async function expectButtonsFit(page: Page, width: number) {
	const boxes = await page.getByTestId('choice').evaluateAll((els) =>
		els.map((el) => {
			const r = el.getBoundingClientRect();
			return { height: r.height, left: r.left, right: r.right, over: el.scrollWidth > el.clientWidth + 1 };
		})
	);
	expect(boxes).toHaveLength(CHOICES.length);
	for (const box of boxes) {
		expect(box.height, `${width}: tap target height`).toBeGreaterThanOrEqual(44);
		expect(box.left, `${width}: left edge`).toBeGreaterThanOrEqual(0);
		expect(box.right, `${width}: right edge`).toBeLessThanOrEqual(width);
		expect(box.over, `${width}: content wider than its button`).toBe(false);
	}
	const scroll = await page.evaluate(() => document.documentElement.scrollWidth);
	expect(scroll, `${width}: page scroll width`).toBeLessThanOrEqual(width);
	if (SHOT_DIR) await page.screenshot({ path: `${SHOT_DIR}/choice-${width}.png`, fullPage: true });
}

// One player for the whole file: sign-ups are rate limited per client.
test('choice problems are answered with large buttons that send the index', async ({ page }) => {
	await signUp(page);
	await serveChoices(page);

	await test.step('buttons fit and wrap at phone and desktop widths', async () => {
		await page.setViewportSize({ width: 320, height: 700 });
		await page.goto('/play');
		await expect(page.getByTestId('choice')).toHaveCount(CHOICES.length);
		await expect(page.getByTestId('math-field')).toHaveCount(0);
		await expect(page.getByRole('group', { name: 'Answer keypad' })).toHaveCount(0);
		await expect(page.getByTestId('choice').nth(2)).toContainText('two thirds of a pie');
		for (const width of [320, 375, 1280]) {
			await page.setViewportSize({ width, height: 800 });
			await expectButtonsFit(page, width);
		}
		await page.setViewportSize({ width: 375, height: 812 });
	});

	await test.step('a wrong choice is turned off, the right one solves it', async () => {
		const sent: unknown[] = [];
		await answerWith(page, [result('incorrect', 2), result('correct', 2)], sent);
		await page.getByTestId('choice').nth(1).click();
		await expect(page.getByTestId('feedback')).toHaveText('So close! Try again.');
		await expect(page.getByTestId('choice').nth(1)).toBeDisabled();
		await expect(page.getByTestId('choice').nth(RIGHT)).toBeEnabled();
		await page.getByTestId('choice').nth(RIGHT).click();
		await expect(page.getByTestId('feedback')).toHaveText("That's right!");
		expect(sent).toEqual([{ choice: 1 }, { choice: RIGHT }]);
		await page.getByRole('button', { name: 'Next' }).click();
	});

	await test.step('out of tries reveals the right choice', async () => {
		const sent: unknown[] = [];
		await answerWith(page, [result('incorrect', 2), result('incorrect', 1), result('incorrect', 0, RIGHT)], sent);
		await expect(page.getByTestId('choice').nth(1)).toBeEnabled();
		for (const index of [1, 2, 3]) {
			await page.getByTestId('choice').nth(index).click();
			await expect.poll(() => sent.length).toBe([1, 2, 3].indexOf(index) + 1);
		}
		await expect(page.getByTestId('revealed-choice')).toContainText('The answer is');
		await expect(page.getByRole('button', { name: 'Next' })).toBeVisible();
		expect(sent).toEqual([{ choice: 1 }, { choice: 2 }, { choice: 3 }]);
	});
});
