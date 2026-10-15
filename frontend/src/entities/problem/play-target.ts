import type { PracticeTarget } from './model';

/** What /play was opened for: an adventure, or practice from the practice picker. */
export interface PlayTarget {
	practice: PracticeTarget | null;
	/** Show the skill's lesson first (the picker's lesson button). */
	lesson: boolean;
}

const SKILL_ID = /^[a-z][a-z0-9_]{0,63}$/;

/** Reads `?skill=<id>` (with `&lesson=1`) or `?weak=1`; anything else is an adventure. */
export function parsePlayTarget(params: URLSearchParams): PlayTarget {
	const skill = params.get('skill');
	if (skill !== null && SKILL_ID.test(skill)) {
		return { practice: { skill_id: skill }, lesson: params.get('lesson') === '1' };
	}
	if (params.get('weak') === '1') return { practice: { weak_spots: true }, lesson: false };
	return { practice: null, lesson: false };
}

/** Where the picker sends a player to practise one skill, or to read its lesson first. */
export function practiceHref(skillId: string, lesson = false): string {
	return `/play?skill=${encodeURIComponent(skillId)}${lesson ? '&lesson=1' : ''}`;
}

export const weakSpotsHref = '/play?weak=1';
