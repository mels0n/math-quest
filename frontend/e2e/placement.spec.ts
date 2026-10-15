import { expect, test, type Page, type Response } from '@playwright/test';

const SHOT_DIR = process.env.E2E_SHOT_DIR;

interface Step {
	done: boolean;
	question?: number;
	problem?: { problem_id: string; skill_id: string; dev_answer_latex: string | null };
	provisional?: string[];
}

const isPlacement = (r: Response) =>
	/\/api\/placement\/(start|answer)$/.test(r.url()) && r.request().method() === 'POST';

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

const fits = () => document.documentElement.scrollWidth <= window.innerWidth;

/** Answers every placement round question, right when `right` says so, until the round ends. */
async function playRound(page: Page, first: Step, right: (step: Step) => boolean): Promise<Step> {
	let step = first;
	for (let asked = 1; !step.done; asked += 1) {
		expect(asked).toBeLessThanOrEqual(15);
		await expect(page.getByTestId('placement-count')).toHaveText(`Puzzle ${asked}`);
		// No hearts, no hints in the placement round, and the answer never reaches the page.
		await expect(page.getByRole('img', { name: /tries left/ })).toHaveCount(0);
		await expect(page.getByRole('button', { name: /hint/i })).toHaveCount(0);
		expect(await page.content()).not.toContain('dev_answer');
		const answer = right(step) ? (step.problem?.dev_answer_latex ?? '') : '99999';
		expect(answer).not.toBe('');
		const pending = page.waitForResponse(isPlacement);
		await typeAnswer(page, answer);
		step = (await (await pending).json()) as Step;
	}
	return step;
}

test('a new player names a grade, takes the placement round, starts ahead, and can retake it', async ({ page }) => {
	const signupWord = process.env.E2E_SIGNUP_WORD ?? '';
	expect(signupWord).not.toBe('');
	await page.setViewportSize({ width: 320, height: 740 });

	await page.goto('/');
	await page.getByRole('button', { name: 'New player', exact: true }).click();
	await expect(page.getByLabel('Nickname', { exact: true })).not.toHaveValue('');
	await page.getByLabel('Secret word from your grown-up').fill(signupWord);
	await tapPin(page, '1234');
	await page.getByRole('button', { name: "Let's go!" }).click();
	await expect(page.getByTestId('recovery-word')).toBeVisible();
	await page.getByRole('button', { name: 'I wrote it down' }).click();

	// The grade question only picks the first placement round puzzle; no age is asked.
	await expect(page.getByRole('heading', { name: 'What grade are you in?' })).toBeVisible();
	expect(await page.evaluate(fits)).toBe(true);
	if (SHOT_DIR) await page.screenshot({ path: `${SHOT_DIR}/placement-grade.png`, fullPage: true });
	const started = page.waitForResponse(isPlacement);
	await page.getByRole('button', { name: 'Grade 2', exact: true }).click();
	await expect(page).toHaveURL(/\/placement\?grade=2$/);
	const first = (await (await started).json()) as Step;
	expect(first.problem?.skill_id).toBe('add_2digit_regroup');
	await expect(page.getByTestId('prompt')).toBeVisible();
	expect(await page.evaluate(fits)).toBe(true);
	if (SHOT_DIR) await page.screenshot({ path: `${SHOT_DIR}/placement-probe.png`, fullPage: true });

	// Something unreadable is asked again and not counted.
	const retried = page.waitForResponse(isPlacement);
	await typeAnswer(page, "1++2");
	const again = (await (await retried).json()) as Step;
	expect(again.problem?.problem_id).toBe(first.problem?.problem_id);
	await expect(page.getByTestId('feedback')).toContainText("couldn't read");

	// Everything but fractions: placed past two-digit addition.
	const done = await playRound(page, again, (s) => s.problem?.skill_id !== 'add_fractions_unlike');
	const result = page.getByTestId('placement-done');
	await expect(result).toBeVisible();
	await expect(page.getByRole('heading', { name: 'ALL SET!' })).toBeFocused();
	await expect(result).toContainText(`You already know ${done.provisional?.length ?? 0} skills!`);
	await expect(result).toContainText('Operation Canyon');
	expect(await page.evaluate(fits)).toBe(true);
	if (SHOT_DIR) await page.screenshot({ path: `${SHOT_DIR}/placement-done.png`, fullPage: true });

	// Play starts past the skills the placement round found.
	const next = page.waitForResponse((r) => r.url().includes('/next') && r.request().method() === 'POST');
	await page.getByRole('button', { name: 'Start adventure' }).click();
	await expect(page).toHaveURL(/\/play$/);
	const firstPlay = (await (await next).json()) as { skill_id: string };
	expect(done.provisional).not.toContain(firstPlay.skill_id);
	await expect(page.getByTestId('solved')).toContainText('0');

	// Finding the level again is offered from settings, but not straight after a round:
	// a friendly line says to come back later (the retake round itself is covered by the
	// backend tests, which can move the clock).
	await page.getByRole('button', { name: 'Settings', exact: true }).click();
	await expect(page).toHaveURL(/\/settings$/);
	expect(await page.evaluate(fits)).toBe(true);
	await page.getByRole('button', { name: 'Find my level again' }).click();
	await expect(page).toHaveURL(/\/placement\?retake=1$/);
	await expect(page.getByRole('heading', { name: 'What grade are you in?' })).toBeVisible();
	await page.getByRole('button', { name: 'Kindergarten' }).click();
	await expect(page.getByRole('alert')).toContainText('Come back in a few minutes');
	await page.getByRole('button', { name: 'Back to play' }).click();
	await expect(page).toHaveURL(/\/play$/);
	await expect(page.getByTestId('prompt').or(page.getByTestId('lesson'))).toBeVisible();
});
