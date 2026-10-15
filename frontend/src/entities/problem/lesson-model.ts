/** Wire shapes of the lesson routes. */

import type { Visual } from '../../shared/visuals';
import type { KeypadProfile, PromptPart, Verdict } from './model';

export interface LessonScreen {
	title: string;
	/** The screen's text as words and math. */
	body: PromptPart[];
	visual: Visual | null;
}

export interface Lesson {
	skill_id: string;
	skill_name: string;
	screens: LessonScreen[];
	worked_example: { prompt: PromptPart[]; steps: PromptPart[][] };
	try_it: { tier: number };
}

/** A lesson's practice problem: checked like a play problem, never scored. */
export interface TryProblem {
	try_id: string;
	skill_id: string;
	skill_name: string;
	prompt: PromptPart[];
	keypad: KeypadProfile;
}

export interface TryResult {
	verdict: Verdict;
	misconception: string | null;
	solved: boolean;
	attempts_left: number;
	/** Sent once the practice problem is solved or out of tries. */
	answer_latex: string | null;
}
