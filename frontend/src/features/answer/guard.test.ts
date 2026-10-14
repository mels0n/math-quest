import { describe, expect, it } from 'vitest';
import { EMPTY_BOX_MESSAGE, noticeAfterEdit, submitBlocker } from './guard';

describe('submitBlocker', () => {
	it('blocks an answer that still has an empty box', () => {
		expect(submitBlocker(String.raw`\frac{3}{\placeholder{}}`)).toBe(EMPTY_BOX_MESSAGE);
		expect(submitBlocker(String.raw`\frac{\placeholder[a]{}}{4}`)).toBe(EMPTY_BOX_MESSAGE);
	});

	it('lets a finished answer through', () => {
		expect(submitBlocker(String.raw`1\,\frac{5}{12}`)).toBeNull();
		expect(submitBlocker('17')).toBeNull();
	});

	it('uses kind copy without em dashes', () => {
		expect(EMPTY_BOX_MESSAGE).not.toContain('—');
	});
});

describe('noticeAfterEdit', () => {
	it('clears the empty-box notice after typing or a keypad tap', () => {
		expect(noticeAfterEdit()).toBe('');
	});
});
