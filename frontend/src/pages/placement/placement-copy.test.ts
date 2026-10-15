import { describe, expect, it } from 'vitest';
import type { PlacementDone } from '../../entities/problem';
import { outcomeLines, progressLabel, retryLine } from './placement-copy';

const done = (provisional: string[], regions: string[]): PlacementDone => ({
	done: true,
	placement_id: 'p',
	frontier: [],
	provisional,
	revealed_regions: regions.map((name, i) => ({ id: `r${i}`, name }))
});

describe('placement copy', () => {
	it('counts the skills placement found', () => {
		expect(outcomeLines(done([], ['Number Meadows']))).toEqual({
			known: "We'll start right at the beginning of the map.",
			places: 'Your adventure starts in Number Meadows.'
		});
		expect(outcomeLines(done(['a'], ['Number Meadows'])).known).toBe('You already know 1 skill!');
		expect(outcomeLines(done(['a', 'b', 'c'], ['Number Meadows', 'Operation Canyon']))).toEqual({
			known: 'You already know 3 skills!',
			places: 'Places to explore: Number Meadows, Operation Canyon.'
		});
	});

	it('shows progress and why an answer was not counted', () => {
		expect(progressLabel({ question: 3, max_questions: 15 })).toBe('Question 3 of up to 15');
		expect(retryLine(null)).toBeNull();
		expect(retryLine('unreadable')).toContain("couldn't read");
		expect(retryLine('wrong_form')).toBe('Try writing it the way the question asks.');
	});
});
