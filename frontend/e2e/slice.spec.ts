import { expect, test, type Page, type Response } from '@playwright/test';

const SHOT_DIR = process.env.E2E_SHOT_DIR;

interface NextBody {
	problem_id: string;
	dev_answer_latex: string | null;
}

const isNext = (r: Response) => r.url().includes('/next') && r.request().method() === 'POST';

async function tapPin(page: Page, pin: string) {
	for (const d of pin) {
		await page.getByRole('group', { name: 'PIN pad' }).getByRole('button', { name: d, exact: true }).click();
	}
}

async function typeAnswer(page: Page, latex: string, viaKeypad = false) {
	const field = page.getByTestId('math-field');
	await expect(field).toBeVisible();
	if (viaKeypad && /^[0-9]+$/.test(latex)) {
		const keypad = page.getByRole('group', { name: 'Answer keypad' });
		for (const d of latex) await keypad.getByRole('button', { name: d, exact: true }).click();
		await page.getByRole('button', { name: 'Go', exact: true }).click();
		return;
	}
	await field.evaluate((el, value) => {
		(el as unknown as { value: string }).value = value;
	}, latex);
	await page.getByRole('button', { name: 'Go', exact: true }).click();
}

test('sign up, see the recovery word, answer three problems, log back in', async ({ page }) => {
	const signupWord = process.env.E2E_SIGNUP_WORD ?? '';
	expect(signupWord).not.toBe('');

	await page.goto('/');
	await expect(page.getByRole('heading', { name: 'MATH QUEST' })).toBeVisible();
	await page.getByRole('button', { name: 'New player', exact: true }).click();
	const nickname = page.getByLabel('Nickname', { exact: true });
	await expect(nickname).not.toHaveValue('');
	const chosenNickname = await nickname.inputValue();
	if (SHOT_DIR) await page.screenshot({ path: `${SHOT_DIR}/task-11-welcome.png` });

	await page.getByLabel('Secret word from your grown-up').fill(signupWord);
	await tapPin(page, '1234');
	await page.getByRole('button', { name: "Let's go!" }).click();

	const word = page.getByTestId('recovery-word');
	await expect(word).toBeVisible();
	const firstWord = (await word.innerText()).trim();
	expect(firstWord.length).toBeGreaterThan(2);

	const firstNext = page.waitForResponse(isNext);
	await page.getByRole('button', { name: 'I wrote it down' }).click();
	await expect(page).toHaveURL(/\/play$/);

	let next = (await (await firstNext).json()) as NextBody;
	for (let round = 0; round < 3; round += 1) {
		expect(next.dev_answer_latex).toBeTruthy();
		const answer = next.dev_answer_latex as string;
		await expect(page.getByTestId('prompt')).toBeVisible();

		if (round === 0) {
			await expect(page.getByTestId('math-field')).toBeVisible();
			if (SHOT_DIR) await page.screenshot({ path: `${SHOT_DIR}/task-11-play.png`, fullPage: true });
			await typeAnswer(page, '12345');
			await expect(page.getByTestId('feedback')).toHaveText('So close! Try again.');
		}

		await typeAnswer(page, answer, round === 1);
		await expect(page.getByTestId('feedback')).toHaveText("That's right!");
		await expect(page.getByRole('progressbar')).toBeVisible();
		expect(await page.content()).not.toContain('dev_answer');

		if (round < 2) {
			const pending = page.waitForResponse(isNext);
			await page.getByRole('button', { name: 'Next' }).click();
			next = (await (await pending).json()) as NextBody;
		}
	}
	await expect(page.getByTestId('solved')).toContainText('3');

	await page.getByRole('button', { name: 'Log out' }).click();
	await expect(page).toHaveURL(/\/$/);
	await expect(page.getByRole('button', { name: 'Log in', exact: true })).toBeVisible();

	await page.getByLabel('Nickname', { exact: true }).fill(chosenNickname);
	await tapPin(page, '1234');
	await page.getByRole('button', { name: 'Play', exact: true }).click();
	await expect(page).toHaveURL(/\/play$/);
	await expect(page.getByTestId('prompt')).toBeVisible();

	// Recovery: forgot the PIN, use the recovery word, get a NEW word shown once.
	await page.getByRole('button', { name: 'Log out' }).click();
	await expect(page).toHaveURL(/\/$/);
	await page.getByRole('button', { name: 'Forgot your PIN?' }).click();
	await page.getByLabel('Nickname', { exact: true }).fill(chosenNickname);
	await page.getByLabel('Recovery word').fill(firstWord);
	await tapPin(page, '5678');
	await page.getByRole('button', { name: 'Get back in' }).click();
	const newWord = page.getByTestId('recovery-word');
	await expect(newWord).toBeVisible();
	expect((await newWord.innerText()).trim()).not.toBe(firstWord);
	await page.getByRole('button', { name: 'I wrote it down' }).click();
	await expect(page).toHaveURL(/\/play$/);
	await expect(page.getByTestId('prompt')).toBeVisible();
});
