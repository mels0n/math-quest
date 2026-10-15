import { describe, expect, it } from 'vitest';
import { focusLine } from './session-copy';

describe('practice focus line', () => {
	it('names the skill being practiced', () => {
		const focus = [{ skill_id: 'add_within_10', name: 'Add to 10' }];
		expect(focusLine(focus, { skill_id: 'add_within_10' })).toBe('Practicing: Add to 10');
	});

	it('says weak spots without listing them', () => {
		const focus = [
			{ skill_id: 'a', name: 'A' },
			{ skill_id: 'b', name: 'B' }
		];
		expect(focusLine(focus, { weak_spots: true })).toBe('Practicing your weak spots');
	});
});
