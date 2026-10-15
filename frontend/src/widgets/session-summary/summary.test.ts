import { describe, expect, it } from 'vitest';
import type { Summary } from '../../entities/problem';
import { accuracyText, durationText, summaryTitle } from './summary';

const base: Summary = {
	type: 'summary',
	session_id: 's',
	mode: 'adventure',
	skills_practiced: [],
	newly_mastered: [],
	problems_solved: 9,
	problems_scored: 11,
	accuracy: 9 / 11,
	seconds: 245
};

describe('session summary copy', () => {
	it('says how long the session took in words', () => {
		expect(durationText(0)).toBe('0 seconds');
		expect(durationText(1)).toBe('1 second');
		expect(durationText(45)).toBe('45 seconds');
		expect(durationText(60)).toBe('1 minute');
		expect(durationText(245)).toBe('4 minutes 5 seconds');
		expect(durationText(121)).toBe('2 minutes 1 second');
	});

	it('shows right answers out of scored ones', () => {
		expect(accuracyText(base)).toBe('9 of 11 (82%)');
		expect(accuracyText({ ...base, accuracy: null, problems_scored: 0, problems_solved: 0 })).toBeNull();
	});

	it('names the kind of session', () => {
		expect(summaryTitle(base)).toBe('QUEST COMPLETE!');
		expect(summaryTitle({ ...base, mode: 'practice' })).toBe('PRACTICE DONE!');
	});
});
