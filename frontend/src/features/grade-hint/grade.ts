import type { GradeHint } from '../../entities/problem';

/** Kid-facing copy of the grade question. */
export const GRADE_COPY = {
	question: 'What grade are you in?',
	why: 'It helps us pick your first puzzle. You can skip it.',
	skip: 'Skip'
} as const;

/** The spoken name of a grade button. */
export function gradeLabel(grade: GradeHint): string {
	return grade === 'K' ? 'Kindergarten' : `Grade ${grade}`;
}

/** Reads a grade from a URL value: a known grade, `null` for a skipped question, or
 * `undefined` when the question has not been answered yet. */
export function parseGrade(raw: string | null, grades: readonly GradeHint[]): GradeHint | null | undefined {
	if (raw === null) return undefined;
	if (raw === 'skip') return null;
	return grades.find((g) => g === raw);
}
