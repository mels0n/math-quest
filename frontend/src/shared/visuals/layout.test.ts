import { describe, expect, test } from 'vitest';
import { figure, jumpSizes, numberLine, overflow } from './layout';
import { VISUAL_KINDS } from './model';
import { LARGEST_VISUALS, SAMPLE_VISUALS } from './samples';

describe('every visual fits its viewBox', () => {
	test('the samples cover every kind', () => {
		expect(new Set(SAMPLE_VISUALS.map((v) => v.kind))).toEqual(new Set(VISUAL_KINDS));
	});

	test.each([...SAMPLE_VISUALS, ...LARGEST_VISUALS].map((v) => [v.kind, v] as const))(
		'%s',
		(_, visual) => {
			const fig = figure(visual);
			expect(fig.width).toBeGreaterThan(0);
			expect(fig.height).toBeGreaterThan(0);
			expect(fig.shapes.length).toBeGreaterThan(0);
			expect(overflow(fig)).toEqual([]);
			expect(fig.label.length).toBeGreaterThan(10);
			expect(fig.label).not.toContain('—');
		}
	);
});

test('a single number means that many jumps of one', () => {
	expect(jumpSizes(3)).toEqual([1, 1, 1]);
	expect(jumpSizes(-2)).toEqual([-1, -1]);
	expect(jumpSizes([2, 3])).toEqual([2, 3]);
});

test('the number line label reads the jumps', () => {
	const fig = numberLine({ min: 0, max: 10, start: 7, jumps: -3, end: 4 });
	expect(fig.label).toBe('Number line from 0 to 10. Start at 7. 3 jumps of 1 to the left. Land on 4.');
	const mixed = numberLine({ min: 0, max: 20, start: 8, jumps: [2, 3], end: 13 });
	expect(mixed.label).toContain('Jumps of 2 right, then 3 right.');
});

test('the overflow check catches a shape outside the box', () => {
	const fig = { width: 10, height: 10, label: 'x', shapes: [{ t: 'circle', cx: 9, cy: 5, r: 3, fill: '#fff' }] } as const;
	expect(overflow({ ...fig, shapes: [...fig.shapes] })).toHaveLength(1);
});
