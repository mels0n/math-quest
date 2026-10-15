import { PLAY_COPY } from '../../entities/problem';
import type { Problem } from '../../entities/problem';

export interface HelpState {
	/** Hint levels already shown on this problem. */
	hintsShown: number;
	/** The learner has answered this problem wrong at least once. */
	missed: boolean;
	/** The problem is solved or out of tries. */
	finished: boolean;
}

export interface HelpButtons {
	hint: boolean;
	/** The hint button's text: the first hint, then the next ones. */
	hintLabel: string;
	explain: boolean;
}

/**
 * Which help buttons a problem shows. Hints are there from the start, one level at a
 * time, until the problem's levels run out. "Explain it another way" is for a learner
 * who is stuck: the server allows it only after a wrong answer. Neither shows once the
 * problem is finished.
 */
export function helpButtons(problem: Problem, state: HelpState): HelpButtons {
	const hintsLeft = Math.max(0, problem.hint_levels - state.hintsShown);
	return {
		hint: !state.finished && hintsLeft > 0,
		hintLabel: state.hintsShown === 0 ? PLAY_COPY.hint : PLAY_COPY.nextHint,
		explain: !state.finished && problem.has_explanations && state.missed
	};
}
