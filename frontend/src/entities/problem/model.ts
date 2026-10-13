/** Wire shapes of the play routes. */

export type Verdict = 'correct' | 'incorrect' | 'wrong_form' | 'unreadable';
export type SkillState = 'locked' | 'ready' | 'learning' | 'mastered' | 'review_due';
export type KeypadProfile = 'numbers' | 'fractions' | 'algebra';

export interface Session {
	session_id: string;
	mode: 'adventure';
	started_at: string;
	problem_count: number;
}

export interface Problem {
	problem_id: string;
	skill_id: string;
	skill_name: string;
	prompt_latex: string;
	keypad: string;
}

export interface Mastery {
	skill_id: string;
	state: SkillState;
	progress: number;
}

export interface AnswerResult {
	verdict: Verdict;
	misconception: string | null;
	solved: boolean;
	attempts_left: number;
	mastery: Mastery;
	answer_latex: string | null;
}

export const MAX_ATTEMPTS = 3;

export function keypadProfile(value: string): KeypadProfile {
	return value === 'fractions' || value === 'algebra' ? value : 'numbers';
}
