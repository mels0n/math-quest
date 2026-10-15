import { describe, expect, it } from 'vitest';
import type { SkillEntry, SkillList } from '../../entities/problem';
import { STATE_LABELS, canPractice, groupByRegion, hasWeakSpots } from './picker';

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
		{ region_id: 'meadows', name: 'Number Meadows' },
		{ region_id: 'empty', name: 'Nowhere' },
		{ region_id: 'canyon', name: 'Operation Canyon' }
	],
	skills: [skill('a', 'meadows', 'mastered'), skill('b', 'canyon', 'locked'), skill('c', 'meadows', 'ready')]
};

describe('skill picker', () => {
	it('groups skills by region in map order and drops empty regions', () => {
		const groups = groupByRegion(list);
		expect(groups.map((g) => g.region_id)).toEqual(['meadows', 'canyon']);
		expect(groups[0]?.skills.map((s) => s.skill_id)).toEqual(['a', 'c']);
	});

	it('never practises a locked skill', () => {
		expect(canPractice(skill('x', 'r', 'locked'))).toBe(false);
		for (const state of ['ready', 'learning', 'provisional', 'mastered', 'review_due'] as const) {
			expect(canPractice(skill('x', 'r', state))).toBe(true);
		}
	});

	it('offers weak spots only with something learning or due', () => {
		expect(hasWeakSpots(list)).toBe(false);
		expect(hasWeakSpots({ ...list, skills: [skill('x', 'meadows', 'learning')] })).toBe(true);
		expect(hasWeakSpots({ ...list, skills: [skill('x', 'meadows', 'review_due')] })).toBe(true);
	});

	it('labels every state with words as well as an icon', () => {
		for (const label of Object.values(STATE_LABELS)) {
			expect(label.text.length).toBeGreaterThan(3);
			expect(label.icon.length).toBeGreaterThan(0);
		}
	});
});
