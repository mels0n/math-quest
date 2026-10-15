import type { PracticeTarget, SkillName } from '../../entities/problem';

export const SESSION_COPY = {
	finish: "I'm done",
	practicing: 'Practicing',
	weakSpots: 'Practicing your weak spots'
} as const;

/** The line above a practice problem: which skill, or that these are weak spots. */
export function focusLine(focus: SkillName[], target: PracticeTarget | null): string {
	if (target && 'weak_spots' in target) return SESSION_COPY.weakSpots;
	return `${SESSION_COPY.practicing}: ${focus.map((s) => s.name).join(', ')}`;
}
