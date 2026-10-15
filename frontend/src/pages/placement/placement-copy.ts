import { feedbackMessage } from '../../entities/problem';
import type { PlacementDone, PlacementStep } from '../../entities/problem';

/** Kid-facing copy of the placement round. */
export const PLACEMENT_COPY = {
	title: 'WARM-UP',
	intro: "A few puzzles to find your starting spot. Just do your best. It's fine not to know some!",
	retake: 'Find your starting spot again',
	loading: 'Getting your puzzles ready',
	doneTitle: 'ALL SET!',
	start: 'Start adventure',
	again: 'Start again',
	closed: 'This warm-up was replaced by a newer one.',
	wrongForm: 'Try writing it the way the question asks.'
} as const;

export function progressLabel(step: Pick<PlacementStep, 'question' | 'max_questions'>): string {
	return `Question ${step.question} of up to ${step.max_questions}`;
}

/** The line under the problem when the last answer was not counted, or null. */
export function retryLine(retry: PlacementStep['retry']): string | null {
	if (retry === 'unreadable') return feedbackMessage('unreadable', null);
	if (retry === 'wrong_form') return PLACEMENT_COPY.wrongForm;
	return null;
}

/** What the finished round tells the learner. Never which answers were right. */
export function outcomeLines(done: PlacementDone): { known: string; places: string } {
	const n = done.provisional.length;
	const known =
		n === 0
			? "We'll start right at the beginning of the map."
			: n === 1
				? 'You already know 1 skill!'
				: `You already know ${n} skills!`;
	const names = done.revealed_regions.map((r) => r.name);
	const places =
		names.length === 1 ? `Your adventure starts in ${names[0]}.` : `Places to explore: ${names.join(', ')}.`;
	return { known, places };
}
