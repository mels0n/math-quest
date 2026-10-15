import type { Visual } from './model';

/** One example of every visual kind, and the largest each kind may be. For tests and demos. */
export const SAMPLE_VISUALS: Visual[] = [
	{ kind: 'number_line', params: { min: 0, max: 20, start: 8, jumps: [2, 3], end: 13 } },
	{ kind: 'base_ten', params: { hundreds: 1, tens: 2, ones: 7 } },
	{ kind: 'fraction_bars', params: { bars: [{ parts: 4, shaded: 3 }, { parts: 8, shaded: 6 }] } },
	{ kind: 'area_model', params: { rows: [20, 3], cols: [10, 4], show_products: true } },
	{ kind: 'algebra_tiles', params: { x2: 1, x: -3, units: 2 } },
	{ kind: 'array', params: { rows: 3, cols: 4 } },
	{ kind: 'clock', params: { hour: 3, minute: 45 } },
	{ kind: 'money', params: { dollars: 1, quarters: 2, dimes: 1, nickels: 1, pennies: 3 } }
];

export const LARGEST_VISUALS: Visual[] = [
	{ kind: 'number_line', params: { min: 0, max: 100, start: 0, jumps: [100], end: 100 } },
	{ kind: 'number_line', params: { min: -10, max: 10, start: 10, jumps: -20, end: -10 } },
	{ kind: 'base_ten', params: { hundreds: 20, tens: 20, ones: 20 } },
	{
		kind: 'fraction_bars',
		params: {
			bars: [
				{ parts: 12, shaded: 12 },
				{ parts: 12, shaded: 0 },
				{ parts: 1, shaded: 1 },
				{ parts: 7, shaded: 3 }
			]
		}
	},
	{ kind: 'area_model', params: { rows: [900, 90, 9], cols: [1000, 1, 1], show_products: true } },
	{ kind: 'algebra_tiles', params: { x2: -10, x: 10, units: -10 } },
	{ kind: 'array', params: { rows: 12, cols: 12 } },
	{ kind: 'clock', params: { hour: 12, minute: 59 } },
	{ kind: 'money', params: { dollars: 10, quarters: 10, dimes: 10, nickels: 10, pennies: 10 } }
];
