/** PIN entry state: collects digits and reports once exactly four have been pressed. */

export const PIN_LENGTH = 4;

export interface PinEntry {
	press: (digit: string) => void;
	backspace: () => void;
	clear: () => void;
	value: () => string;
}

export function createPinEntry(onComplete: (pin: string) => void): PinEntry {
	let digits = '';
	return {
		press(digit) {
			if (!/^[0-9]$/.test(digit) || digits.length >= PIN_LENGTH) return;
			digits += digit;
			if (digits.length === PIN_LENGTH) onComplete(digits);
		},
		backspace() {
			digits = digits.slice(0, -1);
		},
		clear() {
			digits = '';
		},
		value: () => digits
	};
}
