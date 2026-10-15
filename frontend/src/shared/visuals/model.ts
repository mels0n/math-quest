/**
 * Wire shapes of lesson and explanation visuals. The backend validates every param
 * (one schema per kind) and fills in templates before sending, so all numbers here
 * are whole numbers within the documented ranges.
 */

export interface NumberLineParams {
	min: number;
	max: number;
	start: number | null;
	/** Jump sizes (negative goes left), or one number n for |n| jumps of one. */
	jumps: number | number[];
	end: number | null;
}

export interface BaseTenParams {
	hundreds: number;
	tens: number;
	ones: number;
}

export interface FractionBarsParams {
	bars: { parts: number; shaded: number }[];
}

export interface AreaModelParams {
	rows: number[];
	cols: number[];
	show_products: boolean;
}

export interface AlgebraTilesParams {
	x2: number;
	x: number;
	units: number;
}

export interface ArrayParams {
	rows: number;
	cols: number;
}

export interface ClockParams {
	hour: number;
	minute: number;
}

export interface MoneyParams {
	dollars: number;
	quarters: number;
	dimes: number;
	nickels: number;
	pennies: number;
}

export type Visual =
	| { kind: 'number_line'; params: NumberLineParams }
	| { kind: 'base_ten'; params: BaseTenParams }
	| { kind: 'fraction_bars'; params: FractionBarsParams }
	| { kind: 'area_model'; params: AreaModelParams }
	| { kind: 'algebra_tiles'; params: AlgebraTilesParams }
	| { kind: 'array'; params: ArrayParams }
	| { kind: 'clock'; params: ClockParams }
	| { kind: 'money'; params: MoneyParams };

export type VisualKind = Visual['kind'];

export const VISUAL_KINDS: readonly VisualKind[] = [
	'number_line',
	'base_ten',
	'fraction_bars',
	'area_model',
	'algebra_tiles',
	'array',
	'clock',
	'money'
];

/** Drawing colours: the game palette, plus the card's ink and line greys. */
export const PALETTE = {
	navy: '#2b2d42',
	navyDeep: '#1d1e30',
	gold: '#ffd166',
	mint: '#06d6a0',
	berry: '#ef476f',
	ink: '#1b1c2b',
	line: '#c9cbdb',
	paper: '#ffffff'
} as const;
