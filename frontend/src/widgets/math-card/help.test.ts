import { describe, expect, it } from 'vitest';
import type { Problem } from '../../entities/problem';
import { helpButtons } from './help';

const problem: Problem = {
	type: 'problem',
	problem_id: 'p',
	skill_id: 'add_within_10',
	skill_name: 'Adding to 10',
	prompt: [{ kind: 'math', value: '3 + 4 = ?' }],
	keypad: 'numpad',
	choices: null,
	has_lesson: true,
	hint_levels: 3,
	has_explanations: true
};

const fresh = { hintsShown: 0, missed: false, finished: false };

describe('helpButtons', () => {
	it('offers a hint from the start and explanations only once stuck', () => {
		expect(helpButtons(problem, fresh)).toEqual({
			hint: true,
			hintLabel: 'Hint',
			explain: false
		});
		expect(helpButtons(problem, { ...fresh, missed: true }).explain).toBe(true);
	});

	it('steps through the hint levels and then offers another way', () => {
		expect(helpButtons(problem, { ...fresh, hintsShown: 1 })).toMatchObject({
			hint: true,
			hintLabel: 'Next hint'
		});
		expect(helpButtons(problem, { ...fresh, hintsShown: 3 })).toMatchObject({
			hint: false,
			explain: true
		});
	});

	it('shows nothing once the problem is finished', () => {
		expect(helpButtons(problem, { hintsShown: 1, missed: true, finished: true })).toMatchObject({
			hint: false,
			explain: false
		});
	});

	it('shows nothing for a problem without hints or explanations', () => {
		const bare = { ...problem, hint_levels: 0, has_explanations: false };
		expect(helpButtons(bare, { ...fresh, missed: true })).toMatchObject({
			hint: false,
			explain: false
		});
	});
});
