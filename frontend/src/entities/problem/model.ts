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

/** One part of a prompt: words shown as wrapping text, or a math expression in LaTeX. */
export interface PromptPart {
	kind: 'text' | 'math';
	value: string;
}

export interface Problem {
	problem_id: string;
	skill_id: string;
	skill_name: string;
	prompt: PromptPart[];
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
	/** The player's saved count of solved problems after this answer. */
	total_solved: number;
}

export const MAX_ATTEMPTS = 3;

export function keypadProfile(value: string): KeypadProfile {
	return value === 'fractions' || value === 'algebra' ? value : 'numbers';
}
