import { describe, expect, it } from 'vitest';
import { MATH_RUN_SELECTOR, MIN_SCALE, fitRuns, fitScale, type FitRun } from './fit-to-width';

describe('fitScale', () => {
	it('leaves content that fits at full size', () => {
		expect(fitScale(100, 200)).toBe(1);
		expect(fitScale(200, 200)).toBe(1);
	});

	it('shrinks wide content to the available width, rounding down', () => {
		expect(fitScale(400, 200)).toBe(0.5);
		expect(fitScale(300, 200)).toBe(0.666);
		expect(300 * fitScale(300, 200)).toBeLessThanOrEqual(200);
	});

	it('never shrinks below the minimum', () => {
		expect(fitScale(10_000, 100)).toBe(MIN_SCALE);
	});

	it('ignores unmeasured or hidden content', () => {
		expect(fitScale(0, 200)).toBe(1);
		expect(fitScale(500, 0)).toBe(1);
		expect(fitScale(Number.NaN, 200)).toBe(1);
	});
});

/** A run whose width follows its font size, like real text. */
function fakeRun(fullWidth: number): FitRun {
	const style = { fontSize: '' };
	const width = () => {
		const m = /^([\d.]+)em$/.exec(style.fontSize);
		return fullWidth * (m ? Number(m[1]) : 1);
	};
	return {
		style,
		get scrollWidth() {
			return Math.ceil(width());
		},
		getBoundingClientRect: () => ({ width: width() })
	};
}

describe('fitRuns', () => {
	it('reads every width before writing any font size', () => {
		const log: string[] = [];
		const run = (name: string): FitRun => {
			const style = { fontSize: '' };
			return {
				style: new Proxy(style, {
					set(target, key, value) {
						if (value !== '') log.push(`write ${name}`);
						return Reflect.set(target, key, value);
					}
				}),
				get scrollWidth() {
					return 600;
				},
				getBoundingClientRect: () => {
					log.push(`read ${name}`);
					return { width: 600 };
				}
			};
		};
		fitRuns({ clientWidth: 300, querySelectorAll: () => [run('a'), run('b')] });
		expect(log).toEqual(['read a', 'read b', 'write a', 'write b']);
	});

	it('shrinks only the runs wider than the container, and they then fit', () => {
		const wide = fakeRun(600);
		const narrow = fakeRun(80);
		const container = { clientWidth: 300, querySelectorAll: () => [wide, narrow] };

		fitRuns(container);

		expect(narrow.style.fontSize).toBe('');
		expect(wide.style.fontSize).not.toBe('');
		expect(wide.getBoundingClientRect().width).toBeLessThanOrEqual(300);
		expect(wide.scrollWidth).toBeLessThanOrEqual(300);
	});

	it('measures at full size again, so a wider container restores the size', () => {
		const run = fakeRun(600);
		const container = { clientWidth: 300, querySelectorAll: () => [run] };
		fitRuns(container);
		expect(run.style.fontSize).not.toBe('');

		container.clientWidth = 800;
		fitRuns(container);
		expect(run.style.fontSize).toBe('');
	});

	it('selects math runs only', () => {
		const selectors: string[] = [];
		fitRuns({
			clientWidth: 100,
			querySelectorAll: (s: string) => {
				selectors.push(s);
				return [];
			}
		});
		expect(selectors).toEqual([MATH_RUN_SELECTOR]);
	});
});
