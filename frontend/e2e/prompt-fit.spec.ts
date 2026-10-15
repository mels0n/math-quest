import { expect, test, type Page } from '@playwright/test';

/**
 * Long prompts must wrap and fit the card at phone and desktop widths, with no
 * horizontal scrolling. The real backend issues each problem; only its prompt text
 * is replaced, so answering and moving on still work.
 */

const SHOT_DIR = process.env.E2E_SHOT_DIR;
const CSRF = { 'X-Requested-With': 'mathquest' };
const NUMBER = '4738261';
const PLACE_VALUE = String.raw`\text{Which digit is in the thousands place of } ${NUMBER}\text{?}`;
const FRACTION_SUM = [
	String.raw`\frac{125}{360}`,
	String.raw`\frac{17}{48}`,
	String.raw`\frac{999}{1000}`,
	String.raw`\frac{5}{12}`,
	String.raw`\frac{73}{144}`,
	String.raw`\frac{11}{30}`,
	String.raw`\frac{2}{3}`
].join('+');
const WIDTHS = [320, 360, 768, 1366];

interface NextBody {
	prompt_latex: string;
	dev_answer_latex: string | null;
}

async function signUp(page: Page) {
	const suggestion = await page.request.get('/api/auth/nickname-suggestion');
	const { nickname } = (await suggestion.json()) as { nickname: string };
	const signup = await page.request.post('/api/auth/signup', {
		headers: CSRF,
		data: { signup_word: process.env.E2E_SIGNUP_WORD ?? '', nickname, pin: '1234' }
	});
	expect(signup.ok()).toBe(true);
}

/** Replaces the prompt of each issued problem with the next one from `prompts`. */
async function servePrompts(page: Page, prompts: string[], answers: string[]) {
	await page.unroute('**/api/play/sessions/*/next');
	await page.route('**/api/play/sessions/*/next', async (route) => {
		const response = await route.fetch();
		const body = (await response.json()) as NextBody;
		answers.push(body.dev_answer_latex ?? '');
		const prompt = prompts.shift();
		await route.fulfill({ response, json: prompt ? { ...body, prompt_latex: prompt } : body });
	});
}

async function settle(page: Page) {
	await page.evaluate(async () => {
		await document.fonts.ready;
		await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
	});
}

async function expectFits(page: Page, label: string, expectedText?: string) {
	await expect(page.getByTestId('prompt').locator('.run').first()).toBeVisible();
	await settle(page);
	const m = await page.evaluate(() => {
		const prompt = document.querySelector('[data-testid="prompt"]') as HTMLElement;
		const box = prompt.getBoundingClientRect();
		const runs = [...prompt.querySelectorAll<HTMLElement>('.run')].map((el) => {
			const r = el.getBoundingClientRect();
			return { left: r.left, right: r.right };
		});
		return {
			promptLeft: box.left,
			promptRight: box.right,
			runs,
			scrollWidth: document.documentElement.scrollWidth,
			innerWidth: window.innerWidth,
			text: (prompt.textContent ?? '').replace(/\s+/g, '')
		};
	});
	expect(m.runs.length, label).toBeGreaterThan(0);
	for (const run of m.runs) {
		expect(run.right, `${label}: run right edge`).toBeLessThanOrEqual(m.promptRight + 0.5);
		expect(run.left, `${label}: run left edge`).toBeGreaterThanOrEqual(m.promptLeft - 0.5);
	}
	expect(m.scrollWidth, `${label}: page scroll width`).toBeLessThanOrEqual(m.innerWidth);
	if (expectedText) expect(m.text, label).toContain(expectedText);
	if (SHOT_DIR) await page.screenshot({ path: `${SHOT_DIR}/prompt-fit-${label}.png`, fullPage: true });
}

async function answerAndGoNext(page: Page, answer: string) {
	const field = page.getByTestId('math-field');
	await expect(field).toBeVisible();
	await field.evaluate((el, value) => {
		(el as unknown as { value: string }).value = value;
	}, answer);
	await page.getByRole('button', { name: 'Go', exact: true }).click();
	await expect(page.getByTestId('feedback')).toHaveText("That's right!");
	await page.getByRole('button', { name: 'Next' }).click();
}

test('long prompts wrap and fit the card at every width', async ({ page }) => {
	await signUp(page);

	for (const width of WIDTHS) {
		const other = width < 700 ? 1366 : 320;
		const answers: string[] = [];
		await servePrompts(page, [PLACE_VALUE, FRACTION_SUM], answers);
		await page.setViewportSize({ width, height: 900 });
		await page.goto('/play');

		await expectFits(page, `place-${width}`, NUMBER);
		await expect(page.getByTestId('prompt')).toContainText('Which digit is in the thousands place of');

		await page.setViewportSize({ width: other, height: 900 });
		await expectFits(page, `place-${width}-resized-${other}`, NUMBER);
		await page.setViewportSize({ width, height: 900 });
		await expectFits(page, `place-${width}-back`, NUMBER);

		await answerAndGoNext(page, answers[0] as string);
		await expect(page.getByTestId('prompt')).not.toContainText('Which digit');
		await expectFits(page, `fractions-${width}`);

		await page.setViewportSize({ width: other, height: 900 });
		await expectFits(page, `fractions-${width}-resized-${other}`);
	}
});
