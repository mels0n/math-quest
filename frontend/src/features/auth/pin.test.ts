import { describe, expect, it } from 'vitest';
import { createPinEntry } from './pin';

describe('PIN pad', () => {
	it('PIN pad emits exactly 4 digits', () => {
		const emitted: string[] = [];
		const pin = createPinEntry((value) => emitted.push(value));
		for (const d of ['1', '2', '3', '4', '5', '6']) pin.press(d);
		expect(emitted).toEqual(['1234']);
		expect(pin.value()).toBe('1234');
	});

	it('ignores anything that is not a single digit', () => {
		const emitted: string[] = [];
		const pin = createPinEntry((value) => emitted.push(value));
		pin.press('a');
		pin.press('12');
		pin.press('');
		expect(pin.value()).toBe('');
		expect(emitted).toEqual([]);
	});

	it('backspace and clear edit the entry, and it can complete again', () => {
		const emitted: string[] = [];
		const pin = createPinEntry((value) => emitted.push(value));
		['1', '2', '3'].forEach(pin.press);
		pin.backspace();
		expect(pin.value()).toBe('12');
		['9', '8'].forEach(pin.press);
		pin.clear();
		['4', '4', '4', '4'].forEach(pin.press);
		expect(emitted).toEqual(['1298', '4444']);
	});
});
