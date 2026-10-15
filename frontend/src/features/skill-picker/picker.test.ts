import { describe, expect, it } from 'vitest';
import type { SkillEntry, SkillList } from '../../entities/problem';
import { STATE_LABELS, canPractice, groupByRegion, hasWeakSpots, lockedLine, practiceLabel } from './picker';

const skill = (skill_id: string, region: string, state: SkillEntry['state']): SkillEntry => ({
	skill_id,
	name: skill_id,
	region,
	state,
	progress: 0,
	has_lesson: false
});

const list: SkillList = {
	regions: [
		{ id: 'meadows', name: 'Number Meadows' },
		{ id: 'empty', name: 'Nowhere' },
		{ id: 'canyon', name: 'Operation Canyon' }
	],
	skills: [
		skill('a', 'meadows', 'mastered'),
		skill('b', 'canyon', 'locked'),
		skill('c', 'meadows', 'learning'),
		skill('d', 'canyon', 'locked')
	]
};

describe('skill picker', () => {
	it('groups skills by region in map order, folds locked ones and drops empty regions', () => {
		const groups = groupByRegion(list);
		expect(groups.map((g) => g.id)).toEqual(['meadows', 'canyon']);
		expect(groups[0]?.skills.map((s) => s.skill_id)).toEqual(['a', 'c']);
		expect(groups[1]?.skills).toEqual([]);
		expect(groups[1]?.locked).toBe(2);
	});

	it('opens only the regions with something to work on', () => {
		expect(groupByRegion(list).map((g) => g.open)).toEqual([true, false]);
	});

	it('never practices a locked skill', () => {
		expect(canPractice(skill('x', 'r', 'locked'))).toBe(false);
		for (const state of ['ready', 'learning', 'provisional', 'mastered', 'review_due'] as const) {
			expect(canPractice(skill('x', 'r', state))).toBe(true);
		}
	});

	it('offers weak spots only with something learning or due', () => {
		expect(hasWeakSpots({ ...list, skills: [skill('x', 'meadows', 'mastered')] })).toBe(false);
		expect(hasWeakSpots({ ...list, skills: [skill('x', 'meadows', 'learning')] })).toBe(true);
		expect(hasWeakSpots({ ...list, skills: [skill('x', 'meadows', 'review_due')] })).toBe(true);
	});

	it('labels every state with words as well as an icon', () => {
		for (const label of Object.values(STATE_LABELS)) {
			expect(label.text.length).toBeGreaterThan(3);
			expect(label.icon.length).toBeGreaterThan(0);
		}
		expect(practiceLabel({ ...skill('x', 'r', 'mastered'), name: 'Add to 10' })).toBe(
			'Practice Add to 10, Mastered'
		);
		expect(lockedLine(1)).toBe('1 more to unlock');
		expect(lockedLine(3)).toBe('3 more to unlock');
	});
});
