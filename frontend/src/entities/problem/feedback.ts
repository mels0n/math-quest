import type { Verdict } from './model';

const COPY: Record<'CORRECT' | 'INCORRECT' | 'WRONG_FORM' | 'UNREADABLE', string> = {
	CORRECT: "That's right!",
	INCORRECT: 'So close! Try again.',
	WRONG_FORM: 'Right number, now write it the way the question asks.',
	UNREADABLE: "I couldn't read that. Check it and try again."
};

/**
 * Kid-facing line for a verdict. Misconception keys are accepted for later
 * targeted hints; until those exist they use the INCORRECT copy.
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
	retry: 'Try again'
} as const;
