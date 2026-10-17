import { expect, test, type Page, type Response } from '@playwright/test';

const SHOT_DIR = process.env.E2E_SHOT_DIR;
const CSRF = { 'X-Requested-With': 'mathquest' };

interface Step {
	done: boolean;
	problem?: {
		skill_id: string;
		dev_answer_latex: string | null;
		dev_answer_choice: number | null;
	};
}

interface NextBody {
	type: 'problem' | 'lesson' | 'summary';
	skill_id?: string;
	dev_answer_latex?: string | null;
	dev_answer_choice?: number | null;
	problems_solved?: number;
}

const isPlacement = (r: Response) =>
	/\/api\/placement\/(start|answer)$/.test(r.url()) && r.request().method() === 'POST';
const isNext = (r: Response) => r.url().includes('/next') && r.request().method() === 'POST';
const isStart = (r: Response) => r.url().endsWith('/api/play/sessions') && r.request().method() === 'POST';
const fits = () => document.documentElement.scrollWidth <= window.innerWidth;

async function tapPin(page: Page, pin: string) {
	for (const d of pin) {
		await page.getByRole('group', { name: 'PIN pad' }).getByRole('button', { name: d, exact: true }).click();
	}
}

async function typeAnswer(page: Page, latex: string) {
	const field = page.getByTestId('math-field');
	await expect(field).toBeVisible();
	await field.evaluate((el, value) => {
		(el as unknown as { value: string }).value = value;
	}, latex);
	await page.getByRole('button', { name: 'Go', exact: true }).click();
}

/** Answers the problem on screen with the answer the test server exposes. */
async function solve(page: Page, next: NextBody) {
	expect(next.type).toBe('problem');
	await expect(page.getByTestId('prompt')).toBeVisible();
	if (next.dev_answer_choice !== null && next.dev_answer_choice !== undefined) {
		await page.getByTestId('choice').nth(next.dev_answer_choice).click();
	} else {
		expect(next.dev_answer_latex).toBeTruthy();
		await typeAnswer(page, next.dev_answer_latex as string);
	}
	await expect(page.getByTestId('feedback')).toHaveText("That's right!");
}

/** Marks every lesson seen, so the adventure goes straight to problems. */
async function seeEveryLesson(page: Page) {
	const skills = await page.request.get('/api/skills', { headers: CSRF });
	expect(skills.ok()).toBe(true);
	const list = (await skills.json()) as { skills: { skill_id: string; has_lesson: boolean }[] };
	for (const skill of list.skills.filter((s) => s.has_lesson)) {
		const seen = await page.request.post(`/api/lessons/${skill.skill_id}/seen`, { headers: CSRF });
		expect(seen.ok()).toBe(true);
	}
}

// One player for the whole file: sign-ups are rate limited per client.
test('placement, a twelve-problem adventure with its summary, then practice from the picker', async ({
	page
}) => {
	const signupWord = process.env.E2E_SIGNUP_WORD ?? '';
	expect(signupWord).not.toBe('');
	await page.setViewportSize({ width: 320, height: 740 });

	await test.step('sign up, name a grade and find their level', async () => {
		await page.goto('/');
		await page.getByRole('button', { name: 'New player', exact: true }).click();
		await expect(page.getByLabel('Nickname', { exact: true })).not.toHaveValue('');
		await page.getByLabel('Secret word from your grown-up').fill(signupWord);
		await tapPin(page, '1234');
		await page.getByRole('button', { name: "Let's go!" }).click();
		await page.getByRole('button', { name: 'I wrote it down' }).click();

		const started = page.waitForResponse(isPlacement);
		await page.getByRole('button', { name: 'Grade 1', exact: true }).click();
		let step = (await (await started).json()) as Step;
		for (let asked = 1; !step.done; asked += 1) {
			expect(asked).toBeLessThanOrEqual(15);
			// Right on everything below fractions.
			const right = step.problem?.skill_id !== 'add_fractions_unlike';
			const pending = page.waitForResponse(isPlacement);
			const choice = step.problem?.dev_answer_choice ?? null;
			if (choice !== null) {
				await page.getByTestId('choice').nth(right ? choice : (choice + 1) % 3).click();
			} else {
				await typeAnswer(page, right ? (step.problem?.dev_answer_latex ?? '') : '99999');
			}
			step = (await (await pending).json()) as Step;
		}
		await expect(page.getByTestId('placement-done')).toBeVisible();
		await seeEveryLesson(page);
	});

	await test.step('twelve problems end with a summary', async () => {
		const first = page.waitForResponse(isNext);
		await page.getByRole('button', { name: 'Start adventure' }).click();
		await expect(page).toHaveURL(/\/play$/);
		let next = (await (await first).json()) as NextBody;
		for (let solved = 1; solved <= 12; solved += 1) {
			await solve(page, next);
			await expect(page.getByTestId('solved')).toContainText(String(solved));
			const pending = page.waitForResponse(isNext);
			await page.getByRole('button', { name: 'Next', exact: true }).click();
			next = (await (await pending).json()) as NextBody;
		}
		expect(next.type).toBe('summary');
		const summary = page.getByTestId('summary');
		await expect(summary).toBeVisible();
		await expect(summary.getByRole('heading', { name: 'QUEST COMPLETE!' })).toBeVisible();
		await expect(page.getByTestId('summary-accuracy')).toHaveText('12 of 12 (100%)');
		await expect(page.getByTestId('summary-skills').locator('li').first()).toBeVisible();
		await expect(page.getByTestId('prompt')).toHaveCount(0);
		expect(await page.evaluate(fits)).toBe(true);
		if (SHOT_DIR) await page.screenshot({ path: `${SHOT_DIR}/summary.png`, fullPage: true });
	});

	await test.step('practice a skill from the picker', async () => {
		await page.getByRole('button', { name: 'Practice', exact: true }).click();
		await expect(page).toHaveURL(/\/practice$/);
		await expect(page.getByTestId('region-number_meadows')).toContainText('Number Meadows');
		// States are shown in words, and locked skills fold into one line per region.
		const meadows = page.getByTestId('region-number_meadows');
		if ((await meadows.getAttribute('open')) === null) await meadows.locator('summary').click();
		const add = page.getByTestId('skill-add_within_10');
		await expect(add).toContainText('Add to 10');
		await expect(add).toContainText(/You know this! Quick check soon|Mastered|Learning/);
		await expect(page.getByTestId('region-fraction_forest')).toContainText('1 more to unlock');
		expect(await page.evaluate(fits)).toBe(true);
		if (SHOT_DIR) await page.screenshot({ path: `${SHOT_DIR}/practice-picker.png`, fullPage: true });
		// Compact enough for a phone: roughly 1800 px with the
		// sixteen Number Meadows skills open (the old one-card-per-row picker was over 2200
		// for nine skills). The margin absorbs font differences between machines.
		expect(await page.evaluate(() => document.documentElement.scrollHeight)).toBeLessThanOrEqual(1900);

		const started = page.waitForResponse(isStart);
		const first = page.waitForResponse(isNext);
		await add.getByRole('button', { name: /^Practice Add to 10, / }).click();
		await expect(page).toHaveURL(/\/play\?skill=add_within_10$/);
		const session = (await (await started).json()) as { mode: string };
		expect(session.mode).toBe('practice');
		const next = (await (await first).json()) as NextBody;
		expect(next.skill_id).toBe('add_within_10');
		await expect(page.getByTestId('practice-focus')).toHaveText('Practicing: Add to 10');
		await solve(page, next);
		expect(await page.evaluate(fits)).toBe(true);
		if (SHOT_DIR) await page.screenshot({ path: `${SHOT_DIR}/practice-problem.png`, fullPage: true });

		// Ending early shows the practice summary.
		await page.getByRole('button', { name: "I'm done" }).click();
		await expect(page.getByTestId('summary').getByRole('heading', { name: 'PRACTICE DONE!' })).toBeVisible();
		await expect(page.getByTestId('summary-accuracy')).toHaveText('1 of 1 (100%)');
		await expect(page.getByRole('heading', { name: 'PRACTICE DONE!' })).toBeFocused();

		// Play again starts a fresh adventure.
		const again = page.waitForResponse(isStart);
		await page.getByRole('button', { name: 'Play again' }).click();
		expect(((await (await again).json()) as { mode: string }).mode).toBe('adventure');
		await expect(page).toHaveURL(/\/play$/);
		await expect(page.getByTestId('prompt')).toBeVisible();

		// Practice is also reachable mid-adventure, from settings.
		await page.getByRole('button', { name: 'Settings', exact: true }).click();
		await page.getByRole('button', { name: 'Practice a skill' }).click();
		await expect(page).toHaveURL(/\/practice$/);
	});
});
