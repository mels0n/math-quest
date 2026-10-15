import type { Verdict } from './model';

const COPY: Record<'CORRECT' | 'INCORRECT' | 'WRONG_FORM' | 'UNREADABLE', string> = {
	CORRECT: "That's right!",
	INCORRECT: 'So close! Try again.',
	WRONG_FORM: 'Right number, now write it the way the question asks.',
	UNREADABLE: "I couldn't read that. Check it and try again."
};

/**
 * Kid-facing verdict line. The misconception key is not used here: feedback on a wrong
 * answer (about the mistake, or pointing to a hint) comes from the server with the
 * answer result, and the play page shows it instead of the INCORRECT line.
 */
export function feedbackMessage(verdict: Verdict | Uppercase<Verdict>, misconception: string | null) {
	void misconception;
	const key = verdict.toUpperCase() as keyof typeof COPY;
	return COPY[key] ?? COPY.INCORRECT;
}

/** Other kid-facing play copy. */
export const PLAY_COPY = {
	revealed: 'Good try! Every mistake helps you learn.',
	loading: 'Getting your quest ready',
	rateLimited: 'Whoa, slow down!',
	retry: 'Try again',
	ok: 'OK',
	replayLesson: 'See the lesson again',
	hint: 'Hint',
	nextHint: 'Next hint',
	explain: 'Explain it another way',
	anotherWay: 'Another way',
	explanation: 'Another way to see it'
} as const;
