/** Wire shapes of the placement routes. */

import type { Problem } from './model';

/** The grades a learner can name; the hint only picks the first placement question. */
export const GRADE_HINTS = ['K', '1', '2', '3', '4', '5', '6', '7', '8'] as const;
export type GradeHint = (typeof GRADE_HINTS)[number];

/** The next placement question. `retry` is set when the last answer could not be counted. */
export interface PlacementStep {
	done: false;
	placement_id: string;
	problem: Problem;
	question: number;
	max_questions: number;
	retry: 'unreadable' | 'wrong_form' | null;
}

export interface Region {
	id: string;
	name: string;
}

/** A finished placement round. It never says which answers were right. */
export interface PlacementDone {
	done: true;
	placement_id: string;
	/** The highest anchor skill passed; empty when none was. */
	frontier: string[];
	/** Skills now marked as already known, to be checked by later review. */
	provisional: string[];
	revealed_regions: Region[];
}

export type PlacementResult = PlacementStep | PlacementDone;
