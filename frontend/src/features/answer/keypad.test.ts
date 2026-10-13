import { describe, expect, it } from 'vitest';
import { keysFor, layoutFor } from './keypad';

const names = (profile: Parameters<typeof keysFor>[0]) => keysFor(profile).map((k) => k.name);

describe('keypad profiles', () => {
	it('numbers has digits, delete and Go only', () => {
		const n = names('numbers');
		expect(n).toEqual(expect.arrayContaining(['0', '9', 'Delete', 'Go']));
		expect(n).not.toContain('Fraction');
	});

	it('fractions adds a fraction template', () => {
		expect(names('fractions')).toContain('Fraction');
		expect(names('fractions')).not.toContain('x');
	});

	it('algebra adds x, power, square root, brackets and equals', () => {
		expect(names('algebra')).toEqual(
			expect.arrayContaining(['x', 'Power', 'Square root', 'Open bracket', 'Close bracket', 'Equals'])
		);
	});

	it('every profile ends with Go', () => {
		for (const p of ['numbers', 'fractions', 'algebra'] as const) {
			expect(keysFor(p).at(-1)?.name).toBe('Go');
		}
	});
});

describe('keypad layout', () => {
	const DIGIT_ORDER = ['7', '8', '9', '4', '5', '6', '1', '2', '3', '0', 'Delete'];

	it('uses the calculator digit order in every profile', () => {
		for (const p of ['numbers', 'fractions', 'algebra'] as const) {
			expect(layoutFor(p).digits.map((k) => k.name)).toEqual(DIGIT_ORDER);
			expect(layoutFor(p).go.name).toBe('Go');
		}
	});

	it('puts profile-specific keys in the extras block', () => {
		expect(layoutFor('numbers').extras).toEqual([]);
		expect(layoutFor('fractions').extras.map((k) => k.name)).toEqual([
			'Fraction',
			'Move left',
			'Move right'
		]);
		expect(layoutFor('algebra').extras.length).toBeLessThanOrEqual(12);
	});
});
