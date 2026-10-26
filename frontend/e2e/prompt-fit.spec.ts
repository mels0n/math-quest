import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { expect, test, type Page } from '@playwright/test';
import { fetchProblem } from './problems';

/**
 * Long prompts must wrap and fit the card at phone and desktop widths, with no
 * horizontal scrolling. The real backend issues each problem; only its prompt is
 * replaced, so answering and moving on still work.
 */

interface PromptPart {
	kind: 'text' | 'math';
	value: string;
}

const SHOT_DIR = process.env.E2E_SHOT_DIR;
const CSRF = { 'X-Requested-With': 'mathquest' };
const NUMBER = '4738261';
const PLACE_VALUE: PromptPart[] = [
	{ kind: 'text', value: 'Which digit is in the thousands place of ' },
	{ kind: 'math', value: NUMBER },
	{ kind: 'text', value: '?' }
];
const FRACTION_SUM_LATEX = [
	String.raw`\frac{125}{360}`,
	String.raw`\frac{17}{48}`,
	String.raw`\frac{999}{1000}`,
	String.raw`\frac{5}{12}`,
	String.raw`\frac{73}{144}`,
	String.raw`\frac{11}{30}`,
	String.raw`\frac{2}{3}`
].join('+');
const FRACTION_SUM: PromptPart[] = [{ kind: 'math', value: FRACTION_SUM_LATEX }];
const WIDTHS = [320, 360, 768, 1366];
/** Phone and laptop viewports every generator's longest prompt is laid out at. */
const VIEWPORTS = [
	{ width: 320, height: 640 },
	{ width: 360, height: 740 },
	{ width: 375, height: 812 },
	{ width: 768, height: 1024 },
	{ width: 1280, height: 800 },
	{ width: 1366, height: 900 }
];

/** The longest prompt of each generator, written by a backend test. */
const LONGEST = JSON.parse(
	readFileSync(
		resolve(dirname(fileURLToPath(import.meta.url)), '../../testdata/longest-prompts.json'),
		'utf8'
	)
) as Record<string, { prompt: PromptPart[] }>;

interface NextBody {
	skill_id: string;
	prompt: PromptPart[];
	dev_answer_latex: string | null;
	dev_answer_choice?: number | null;
}

/** How the real problem under a replaced prompt is answered: typed, or by choice index. */
interface Answer {
	skill: string;
	latex: string;
	choice: number | null;
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
async function servePrompts(page: Page, prompts: PromptPart[][], answers: Answer[]) {
	await page.unroute('**/api/play/sessions/*/next');
	await page.route('**/api/play/sessions/*/next', async (route) => {
		const fetched = await fetchProblem(page, route);
		const response = fetched.response;
		const body = fetched.body as unknown as NextBody;
		answers.push({
			skill: body.skill_id,
			latex: body.dev_answer_latex ?? '',
			choice: body.dev_answer_choice ?? null
		});
		const prompt = prompts.shift();
		await route.fulfill({ response, json: prompt ? { ...body, prompt } : body });
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
			const overflowY = getComputedStyle(el).overflowY;
			const scrollsY =
				(overflowY === 'auto' || overflowY === 'scroll') && el.scrollHeight > el.clientHeight + 1;
			return { left: r.left, right: r.right, scroll: el.scrollWidth, client: el.clientWidth, scrollsY };
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
		// A math run that only fits by scrolling inside itself would hide digits.
		expect(run.scroll, `${label}: run scrolls`).toBeLessThanOrEqual(run.client + 1);
		expect(run.scrollsY, `${label}: run scrolls vertically`).toBe(false);
	}
	expect(m.scrollWidth, `${label}: page scroll width`).toBeLessThanOrEqual(m.innerWidth);
	if (expectedText) expect(m.text, label).toContain(expectedText);
	if (SHOT_DIR) await page.screenshot({ path: `${SHOT_DIR}/prompt-fit-${label}.png`, fullPage: true });
}

/** No element in the card is wider than its box, and the page does not scroll sideways. */
async function expectNoOverflow(page: Page, label: string) {
	await expect(page.getByTestId('prompt').locator('.run').first()).toBeVisible();
	await settle(page);
	const m = await page.evaluate(() => {
		const card = document.querySelector('section.card') as HTMLElement;
		const over = [card, ...card.querySelectorAll<HTMLElement>('*')]
			.filter((el) => getComputedStyle(el).display !== 'inline')
			.filter((el) => el.scrollWidth > el.clientWidth + 1)
			.map((el) => `${el.tagName.toLowerCase()}.${el.className}: ${el.scrollWidth}>${el.clientWidth}`);
		// A box that scrolls vertically shows a scrollbar beside the math and hides part of it.
		const scrollers = [card, ...card.querySelectorAll<HTMLElement>('*')]
			.filter((el) => ['auto', 'scroll'].includes(getComputedStyle(el).overflowY))
			.filter((el) => el.scrollHeight > el.clientHeight + 1)
			.map((el) => `${el.tagName.toLowerCase()}.${el.className}: ${el.scrollHeight}>${el.clientHeight}`);
		return {
			over,
			scrollers,
			scrollWidth: document.documentElement.scrollWidth,
			innerWidth: window.innerWidth
		};
	});
	expect(m.over, `${label}: elements wider than their box`).toEqual([]);
	expect(m.scrollers, `${label}: elements scrolling vertically`).toEqual([]);
	expect(m.scrollWidth, `${label}: page scroll width`).toBeLessThanOrEqual(m.innerWidth);
	if (SHOT_DIR) await page.screenshot({ path: `${SHOT_DIR}/longest-${label}.png`, fullPage: true });
}

/**
 * The server takes 60 answers a minute from one player (ANSWER_LIMIT in
 * backend/src/mathquest/api/ratelimit.py), and laying out every generator's prompt
 * answers more than that. Answers wait, when they must, to stay under it: five under
 * the limit and a second over its window, for clock and latency skew. The count spans
 * the whole file, so it can only wait more than needed.
 */
const ANSWERS_PER_WINDOW = 55;
const ANSWER_WINDOW_MS = 61_000;
const answeredAt: number[] = [];

async function paceAnswers(page: Page) {
	const now = Date.now();
	while (answeredAt.length > 0 && (answeredAt[0] as number) <= now - ANSWER_WINDOW_MS) {
		answeredAt.shift();
	}
	if (answeredAt.length >= ANSWERS_PER_WINDOW) {
		await page.waitForTimeout((answeredAt.shift() as number) + ANSWER_WINDOW_MS - now);
	}
	answeredAt.push(Date.now());
}

async function answerAndGoNext(page: Page, answer: Answer) {
	await paceAnswers(page);
	const scored = page
		.waitForResponse((r) => /\/api\/play\/problems\/[^/]+\/answer$/.test(r.url()), {
			timeout: 15_000
		})
		.catch(() => null);
	if (answer.choice !== null) {
		await page.getByTestId('choice').nth(answer.choice).click();
	} else {
		const field = page.getByTestId('math-field');
		await expect(field).toBeVisible();
		await field.evaluate((el, value) => {
			(el as unknown as { value: string }).value = value;
		}, answer.latex);
		await page.getByRole('button', { name: 'Go', exact: true }).click();
	}
	// Name the real problem and the server's reply, so a failure says which skill broke.
	const reply = await scored;
	const body = reply ? await reply.text().catch(() => '(body unavailable)') : '';
	const said = `${answer.skill} answered ${JSON.stringify(answer)}: ${
		reply ? `${reply.status()} ${body}` : 'no answer response within 15 s'
	}`;
	await expect(page.getByTestId('feedback'), said).toHaveText("That's right!");
	await page.getByRole('button', { name: 'Next' }).click();
}

test('long prompts wrap and fit the card at every width', async ({ page }) => {
	await signUp(page);

	for (const width of WIDTHS) {
		const other = width < 700 ? 1366 : 320;
		const answers: Answer[] = [];
		await servePrompts(page, [PLACE_VALUE, FRACTION_SUM], answers);
		await page.setViewportSize({ width, height: 900 });
		await page.goto('/play');

		await expectFits(page, `place-${width}`, NUMBER);
		await expect(page.getByTestId('prompt')).toContainText('Which digit is in the thousands place of');

		await page.setViewportSize({ width: other, height: 900 });
		await expectFits(page, `place-${width}-resized-${other}`, NUMBER);
		await page.setViewportSize({ width, height: 900 });
		await expectFits(page, `place-${width}-back`, NUMBER);

		await answerAndGoNext(page, answers[0] as Answer);
		await expect(page.getByTestId('prompt')).not.toContainText('Which digit');
		await expectFits(page, `fractions-${width}`);

		await page.setViewportSize({ width: other, height: 900 });
		await expectFits(page, `fractions-${width}-resized-${other}`);
	}
});

test("every generator's longest prompt fits the card at phone and desktop sizes", async ({
	page
}) => {
	test.setTimeout(240_000);
	await signUp(page);
	const skills = Object.keys(LONGEST).sort();
	expect(skills.length).toBeGreaterThanOrEqual(20);
	// A quest ends after a fixed number of problems, so the prompts are laid out in
	// chunks, each in its own quest (every visit to /play starts a new one). CHUNK must
	// stay at or below SESSION_PROBLEMS (12) in backend/src/mathquest/engine/scheduler.py.
	const CHUNK = 8;
	for (let start = 0; start < skills.length; start += CHUNK) {
		const chunk = skills.slice(start, start + CHUNK);
		const answers: Answer[] = [];
		await servePrompts(
			page,
			chunk.map((s) => (LONGEST[s] as { prompt: PromptPart[] }).prompt),
			answers
		);
		await page.setViewportSize(VIEWPORTS[0] as { width: number; height: number });
		await page.goto('/play');

		for (const [i, skill] of chunk.entries()) {
			const text = (LONGEST[skill] as { prompt: PromptPart[] }).prompt
				.filter((p) => p.kind === 'text')
				.map((p) => p.value.trim())
				.join(' ');
			if (text) await expect(page.getByTestId('prompt')).toContainText(text.split(' ')[0] as string);
			for (const size of VIEWPORTS) {
				await page.setViewportSize(size);
				await expectNoOverflow(page, `${skill}-${size.width}x${size.height}`);
			}
			await page.setViewportSize(VIEWPORTS[0] as { width: number; height: number });
			if (i < chunk.length - 1) {
				const before = await page.getByTestId('prompt').textContent();
				await answerAndGoNext(page, answers[i] as Answer);
				if (before) await expect(page.getByTestId('prompt')).not.toHaveText(before);
			}
		}
	}
});

