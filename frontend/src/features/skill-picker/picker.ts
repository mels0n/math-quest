import type { SkillEntry, SkillList, SkillState } from '../../entities/problem';

/** Each state gets an icon and words, so color is never the only signal. */
export const STATE_LABELS: Record<SkillState, { icon: string; text: string }> = {
	locked: { icon: '\u{1F512}', text: 'Locked' },
	ready: { icon: '▶', text: 'Ready to start' },
	learning: { icon: '✎', text: 'Learning' },
	provisional: { icon: '✓', text: 'You know this! Quick check soon' },
	mastered: { icon: '★', text: 'Mastered' },
	review_due: { icon: '↻', text: 'Time to review' }
};

export const PICKER_COPY = {
	intro: 'Pick a skill to practice. No timer here. Take your time.',
	weakSpots: 'My weak spots',
	weakSpotsWhy: 'Skills to learn and reviews due.',
	noWeakSpots: 'No weak spots right now. Pick any skill below!',
	practice: 'Practice',
	lesson: 'Lesson',
	back: 'Back to play'
} as const;

export interface RegionGroup {
	id: string;
	name: string;
	/** Skills that can be practiced, in map order. */
	skills: SkillEntry[];
	/** How many skills of the region are still locked. */
	locked: number;
	/** Open at first: the region has a skill being learned or due for review. */
	open: boolean;
}

export function canPractice(skill: SkillEntry): boolean {
	return skill.state !== 'locked';
}

function needsWork(skill: SkillEntry): boolean {
	return skill.state === 'learning' || skill.state === 'review_due';
}

/** Skills grouped by region in map order; regions with no skills are left out. */
export function groupByRegion(list: SkillList): RegionGroup[] {
	return list.regions
		.map((r) => {
			const all = list.skills.filter((s) => s.region === r.id);
			return {
				id: r.id,
				name: r.name,
				skills: all.filter(canPractice),
				locked: all.filter((s) => !canPractice(s)).length,
				open: all.some(needsWork)
			};
		})
		.filter((g) => g.skills.length + g.locked > 0);
}

/** "My weak spots" has something to work on: a skill being learned or a review due. */
export function hasWeakSpots(list: SkillList): boolean {
	return list.skills.some(needsWork);
}

/** The card's spoken name: what it does, which skill, and its state. */
export function practiceLabel(skill: SkillEntry): string {
	return `${PICKER_COPY.practice} ${skill.name}, ${STATE_LABELS[skill.state].text}`;
}

export function lockedLine(count: number): string {
	return count === 1 ? '1 more to unlock' : `${count} more to unlock`;
}
