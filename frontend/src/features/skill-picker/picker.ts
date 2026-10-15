import type { SkillEntry, SkillList, SkillState } from '../../entities/problem';

/** Each state gets an icon and words, so color is never the only signal. */
export const STATE_LABELS: Record<SkillState, { icon: string; text: string }> = {
	locked: { icon: '\u{1F512}', text: 'Locked' },
	ready: { icon: '▶', text: 'Ready to start' },
	learning: { icon: '✎', text: 'Learning' },
	provisional: { icon: '✓', text: 'Known, check coming up' },
	mastered: { icon: '★', text: 'Mastered' },
	review_due: { icon: '↻', text: 'Time to review' }
};

export const PICKER_COPY = {
	intro: 'Pick a skill to practice. No timer here, take your time.',
	weakSpots: 'My weak spots',
	weakSpotsWhy: 'Skills you are still learning and reviews that are due.',
	noWeakSpots: 'No weak spots right now. Pick any skill below!',
	practice: 'Practice',
	lesson: 'Lesson',
	back: 'Back to adventure'
} as const;

export interface RegionGroup {
	region_id: string;
	name: string;
	skills: SkillEntry[];
}

/** Skills grouped by region in map order; regions with no skills are left out. */
export function groupByRegion(list: SkillList): RegionGroup[] {
	return list.regions
		.map((r) => ({
			region_id: r.region_id,
			name: r.name,
			skills: list.skills.filter((s) => s.region === r.region_id)
		}))
		.filter((g) => g.skills.length > 0);
}

export function canPractice(skill: SkillEntry): boolean {
	return skill.state !== 'locked';
}

/** "My weak spots" has something to work on: a skill being learned or a review due. */
export function hasWeakSpots(list: SkillList): boolean {
	return list.skills.some((s) => s.state === 'learning' || s.state === 'review_due');
}
