import { expect, test } from 'vitest';
import { LESSON_COPY, lessonSteps } from './steps';

test('screens come first, then the worked example, then the try-it', () => {
	expect(lessonSteps(3)).toEqual([
		{ kind: 'screen', index: 0 },
		{ kind: 'screen', index: 1 },
		{ kind: 'screen', index: 2 },
		{ kind: 'worked' },
		{ kind: 'try' }
	]);
});

test('lesson copy has no em dash', () => {
	for (const text of Object.values(LESSON_COPY)) expect(text).not.toContain('—');
});
