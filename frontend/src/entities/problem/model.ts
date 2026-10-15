/** Wire shapes of the play routes. */

import type { Visual } from '../../shared/visuals';

export type Verdict = 'correct' | 'incorrect' | 'wrong_form' | 'unreadable';
export type SkillState =
	| 'locked'
	| 'ready'
	| 'learning'
	| 'mastered'
	| 'review_due'
	| 'provisional';
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
	/** How many hint levels the problem offers (0 for none). */
	hint_levels: number;
	/** The problem offers "explain it another way". */
	has_explanations: boolean;
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

/** What to tell the learner after a wrong answer; never states the answer. */
export interface Feedback {
	/** About the mistake made, a pointer to the Hint button, or a plain try-again. */
	kind: 'misconception' | 'hint' | 'retry';
	text: PromptPart[];
}

export interface AnswerResult {
	verdict: Verdict;
	misconception: string | null;
	feedback: Feedback | null;
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

/** One hint level: 1 nudges, 2 gives the next step, 3 works this problem through. */
export interface Hint {
	level: number;
	levels: number;
	text: PromptPart[];
}

/** One way of explaining the skill, with this problem's numbers. */
export interface Explanation {
	approach: number;
	approaches: number;
	style: 'visual' | 'steps' | 'story' | 'worked';
	/** Words and math with simple Markdown (paragraphs, lists). */
	body: PromptPart[];
	visual: Visual | null;
}
