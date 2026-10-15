/** Wire shapes of the play routes. */

export type Verdict = 'correct' | 'incorrect' | 'wrong_form' | 'unreadable';
export type SkillState = 'locked' | 'ready' | 'learning' | 'mastered' | 'review_due';
/** Keypad profiles a skill can ask for; `choice` means answer buttons, no keypad. */
export const KEYPAD_PROFILES = [
	'numpad',
	'numpad_neg',
	'fraction',
	'mixed',
	'decimal',
	'exponent',
	'algebra',
	'choice'
] as const;
export type KeypadProfile = (typeof KEYPAD_PROFILES)[number];

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
	type: 'problem';
	problem_id: string;
	skill_id: string;
	skill_name: string;
	prompt: PromptPart[];
	keypad: KeypadProfile;
	/** Set only for a multiple-choice problem, which is answered with a choice index. */
	choices: PromptPart[][] | null;
	/** The skill has a lesson the learner can replay. */
	has_lesson: boolean;
}

/** Shown instead of a problem before the first problem of a skill with an unseen lesson. */
export interface LessonDue {
	type: 'lesson';
	skill_id: string;
	skill_name: string;
}

/** What asking for the next problem returns. */
export type NextItem = Problem | LessonDue;

/** What the learner sends: typed LaTeX, or the index of a choice. */
export type Answer = { latex: string } | { choice: number };

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
	/** The right choice's index, revealed once a choice problem is scored. */
	answer_choice: number | null;
	/** The player's saved count of solved problems after this answer. */
	total_solved: number;
}

export const MAX_ATTEMPTS = 3;

/** The profile named by `value`; anything unknown gets the plain number pad. */
export function keypadProfile(value: string): KeypadProfile {
	return (KEYPAD_PROFILES as readonly string[]).includes(value)
		? (value as KeypadProfile)
		: 'numpad';
}
