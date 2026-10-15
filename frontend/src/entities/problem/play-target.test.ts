import { describe, expect, it } from 'vitest';
import { parsePlayTarget, practiceHref } from './play-target';

const parse = (query: string) => parsePlayTarget(new URLSearchParams(query));

describe('play target', () => {
	it('is an adventure by default', () => {
		expect(parse('')).toEqual({ practice: null, lesson: false });
		expect(parse('skill=Bad-Id')).toEqual({ practice: null, lesson: false });
		expect(parse('weak=yes')).toEqual({ practice: null, lesson: false });
	});

	it('practises one skill, with its lesson first when asked', () => {
		expect(parse('skill=add_within_10')).toEqual({
			practice: { skill_id: 'add_within_10' },
			lesson: false
		});
		expect(parse(practiceHref('add_within_10', true).split('?')[1] ?? '')).toEqual({
			practice: { skill_id: 'add_within_10' },
			lesson: true
		});
	});

	it('practises weak spots', () => {
		expect(parse('weak=1')).toEqual({ practice: { weak_spots: true }, lesson: false });
	});
});
