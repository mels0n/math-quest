import { describe, expect, it } from 'vitest';
import { GRADE_HINTS } from '../../entities/problem';
import { gradeLabel, parseGrade } from './grade';

describe('grade hint', () => {
	it('names every grade', () => {
		expect(GRADE_HINTS.map(gradeLabel)).toEqual([
			'Kindergarten',
			'Grade 1',
			'Grade 2',
			'Grade 3',
			'Grade 4',
			'Grade 5',
			'Grade 6',
			'Grade 7',
			'Grade 8'
		]);
	});

	it('reads a grade from the address', () => {
		expect(parseGrade('3', GRADE_HINTS)).toBe('3');
		expect(parseGrade('K', GRADE_HINTS)).toBe('K');
		expect(parseGrade('skip', GRADE_HINTS)).toBeNull();
		expect(parseGrade(null, GRADE_HINTS)).toBeUndefined();
		expect(parseGrade('12', GRADE_HINTS)).toBeUndefined();
		expect(parseGrade('k', GRADE_HINTS)).toBeUndefined();
	});
});
