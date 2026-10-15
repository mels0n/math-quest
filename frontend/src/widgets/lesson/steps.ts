/** The pages of a lesson: its screens, then the worked example, then "you try". */
export type LessonStep =
	| { kind: 'screen'; index: number }
	| { kind: 'worked' }
	| { kind: 'try' };

export function lessonSteps(screenCount: number): LessonStep[] {
	return [
		...Array.from({ length: screenCount }, (_, index) => ({ kind: 'screen', index }) as const),
		{ kind: 'worked' },
		{ kind: 'try' }
	];
}

/** Kid-facing lesson copy, in one place. */
export const LESSON_COPY = {
	back: 'Back',
	next: 'Next',
	nextStep: 'Show the next step',
	worked: "Let's do one together",
	tryIt: 'Your turn!',
	done: 'Start playing',
	doneReplay: 'Back to my problem',
	screenOf: (n: number, total: number) => `Screen ${n} of ${total}`
} as const;
