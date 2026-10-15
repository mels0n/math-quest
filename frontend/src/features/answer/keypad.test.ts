import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { KEYPAD_PROFILES, keypadProfile, type KeypadProfile } from '../../entities/problem';
import { keysFor, layoutFor } from './keypad';

const names = (profile: KeypadProfile) => keysFor(profile).map((k) => k.name);
const WITH_KEYS = KEYPAD_PROFILES.filter((p) => p !== 'choice');

describe('keypad profiles', () => {
	it('numpad has digits, delete and Go only', () => {
		const n = names('numpad');
		expect(n).toEqual(expect.arrayContaining(['0', '9', 'Delete', 'Go']));
		expect(n).toHaveLength(12);
	});

	it('numpad_neg adds a minus key', () => {
		expect(layoutFor('numpad_neg')?.extras.map((k) => k.name)).toEqual(['Minus']);
	});

	it('fraction adds a fraction template', () => {
		expect(names('fraction')).toContain('Fraction');
		expect(names('fraction')).not.toContain('x');
	});

	it('mixed adds a mixed-number template next to the fraction', () => {
		expect(names('mixed')).toEqual(expect.arrayContaining(['Mixed number', 'Fraction']));
	});

	it('decimal adds a decimal point and minus', () => {
		expect(layoutFor('decimal')?.extras.map((k) => k.name)).toEqual(['Decimal point', 'Minus']);
	});

	it('exponent adds power, square root and brackets', () => {
		expect(names('exponent')).toEqual(
			expect.arrayContaining(['Power', 'Square root', 'Open bracket', 'Close bracket', 'Minus'])
		);
		expect(names('exponent')).not.toContain('x');
	});

	it('algebra adds x, y, signs, equals, power, root, brackets and fraction', () => {
		expect(names('algebra')).toEqual(
			expect.arrayContaining([
				'x',
				'y',
				'Plus',
				'Minus',
				'Equals',
				'Power',
				'Square root',
				'Open bracket',
				'Close bracket',
				'Fraction'
			])
		);
	});

	it('choice has no keypad', () => {
		expect(layoutFor('choice')).toBeNull();
		expect(keysFor('choice')).toEqual([]);
	});

	it('every keypad ends with Go', () => {
		for (const p of WITH_KEYS) expect(keysFor(p).at(-1)?.name).toBe('Go');
	});

	it('keypadProfile accepts all eight profiles and falls back to numpad', () => {
		expect(KEYPAD_PROFILES).toHaveLength(8);
		for (const p of KEYPAD_PROFILES) expect(keypadProfile(p)).toBe(p);
		expect(keypadProfile('numbers')).toBe('numpad');
		expect(keypadProfile('')).toBe('numpad');
	});
});

describe('keypad layout', () => {
	const DIGIT_ORDER = ['7', '8', '9', '4', '5', '6', '1', '2', '3', '0', 'Delete'];

	it('uses the calculator digit order in every profile', () => {
		for (const p of WITH_KEYS) {
			expect(layoutFor(p)?.digits.map((k) => k.name)).toEqual(DIGIT_ORDER);
			expect(layoutFor(p)?.go.name).toBe('Go');
		}
	});

	it('puts profile-specific keys in the extras block', () => {
		expect(layoutFor('numpad')?.extras).toEqual([]);
		expect(layoutFor('fraction')?.extras.map((k) => k.name)).toEqual([
			'Fraction',
			'Move left',
			'Move right'
		]);
		for (const p of WITH_KEYS) expect(layoutFor(p)?.extras.length).toBeLessThanOrEqual(12);
	});
});

describe('insert keys', () => {
	const inserts = (p: KeypadProfile) =>
		Object.fromEntries(
			keysFor(p).flatMap((k) => (k.action.kind === 'insert' ? [[k.name, k.action.latex]] : []))
		);
	const digits = Object.fromEntries('0123456789'.split('').map((d) => [d, d]));

	it('inserts the exact latex for every key', () => {
		expect(inserts('numpad')).toEqual(digits);
		expect(inserts('numpad_neg')).toEqual({ ...digits, Minus: '-' });
		expect(inserts('fraction')).toEqual({ ...digits, Fraction: String.raw`\frac{#0}{#?}` });
		expect(inserts('mixed')).toEqual({
			...digits,
			'Mixed number': String.raw`#?\frac{#?}{#?}`,
			Fraction: String.raw`\frac{#0}{#?}`
		});
		expect(inserts('decimal')).toEqual({ ...digits, 'Decimal point': '.', Minus: '-' });
		expect(inserts('exponent')).toEqual({
			...digits,
			Power: '^{#?}',
			'Square root': String.raw`\sqrt{#0}`,
			Minus: '-',
			'Open bracket': '(',
			'Close bracket': ')'
		});
		expect(inserts('algebra')).toEqual({
			...digits,
			x: 'x',
			y: 'y',
			Plus: '+',
			Minus: '-',
			Equals: '=',
			Power: '^{#?}',
			'Square root': String.raw`\sqrt{#0}`,
			'Open bracket': '(',
			'Close bracket': ')',
			Fraction: String.raw`\frac{#0}{#?}`
		});
	});
});

describe('shared keypad samples', () => {
	interface Sample {
		keys: string[];
		latex: string;
	}
	const file = resolve(
		dirname(fileURLToPath(import.meta.url)),
		'../../../../testdata/keypad-samples.json'
	);
	const samples = (JSON.parse(readFileSync(file, 'utf8')) as { profiles: Record<string, Sample[]> })
		.profiles;

	it('has samples for every profile with keys, and none for choice', () => {
		expect(Object.keys(samples).sort()).toEqual([...KEYPAD_PROFILES].sort());
		for (const p of WITH_KEYS) expect(samples[p]?.length, p).toBeGreaterThan(0);
		expect(samples.choice).toEqual([]);
	});

	it('every sample taps only keys its profile offers', () => {
		for (const p of KEYPAD_PROFILES) {
			const offered = new Set(names(p));
			for (const sample of samples[p] ?? []) {
				for (const key of sample.keys) expect(offered.has(key), `${p}: ${key}`).toBe(true);
			}
		}
	});
});
