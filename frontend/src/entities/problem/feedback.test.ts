import { describe, expect, it } from 'vitest';
import { feedbackMessage } from './feedback';

describe('feedbackMessage', () => {
	it('feedback message for each verdict', () => {
		expect(feedbackMessage('CORRECT', null)).toBe("That's right!");
		expect(feedbackMessage('INCORRECT', null)).toBe('So close! Try again.');
		expect(feedbackMessage('WRONG_FORM', null)).toMatch(/Right number/);
		expect(feedbackMessage('UNREADABLE', null)).toMatch(/couldn't read/i);
	});

	it('misconception keys fall back to the INCORRECT copy', () => {
		expect(feedbackMessage('INCORRECT', 'added_denominators')).toBe(
			feedbackMessage('INCORRECT', null)
		);
	});

	it('accepts the lowercase wire values from the API', () => {
		expect(feedbackMessage('correct', null)).toBe("That's right!");
		expect(feedbackMessage('wrong_form', null)).toMatch(/Right number/);
	});

	it('has no em dashes in any copy', () => {
		for (const v of ['CORRECT', 'INCORRECT', 'WRONG_FORM', 'UNREADABLE'] as const) {
			expect(feedbackMessage(v, null)).not.toContain('—');
		}
	});
});
