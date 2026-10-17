import type { KeypadProfile } from '../../entities/problem';

export type KeyAction =
	| {
			kind: 'insert';
			latex: string;
			/**
			 * The digits just before the caret become the template's `#0`, so tapping 1 5, the
			 * key, then 3 4 writes 15 over 34.
			 */
			wrapNumber?: boolean;
	  }
	| { kind: 'command'; command: 'deleteBackward' | 'moveToPreviousChar' | 'moveToNextChar' }
	| { kind: 'go' };

export interface Key {
	label: string;
	name: string;
	action: KeyAction;
	tone?: 'gold' | 'mint' | 'aux';
}

const digit = (d: string): Key => ({ label: d, name: d, action: { kind: 'insert', latex: d } });
const insert = (label: string, name: string, latex: string, wrapNumber?: boolean): Key => ({
	label,
	name,
	action: wrapNumber ? { kind: 'insert', latex, wrapNumber } : { kind: 'insert', latex },
	tone: 'aux'
});

const FRAC = String.raw`\frac{#0}{#?}`;

/** Calculator order: 7 8 9 / 4 5 6 / 1 2 3, then 0 and delete on the bottom row. */
const DIGITS = ['7', '8', '9', '4', '5', '6', '1', '2', '3', '0'].map(digit);

const BACKSPACE: Key = {
	label: '⌫',
	name: 'Delete',
	action: { kind: 'command', command: 'deleteBackward' },
	tone: 'aux'
};
const GO: Key = { label: 'Go', name: 'Go', action: { kind: 'go' }, tone: 'mint' };
const LEFT: Key = {
	label: '◀',
	name: 'Move left',
	action: { kind: 'command', command: 'moveToPreviousChar' },
	tone: 'aux'
};
const RIGHT: Key = {
	label: '▶',
	name: 'Move right',
	action: { kind: 'command', command: 'moveToNextChar' },
	tone: 'aux'
};

const FRACTION = insert('⁄', 'Fraction', FRAC, true);
/**
 * On the mixed keypad 2, Fraction, 1, move right, 3 means 2 and one third (the shared
 * samples pin that), so its Fraction key never wraps the digits before it.
 */
const FRACTION_AFTER_WHOLE = insert('⁄', 'Fraction', FRAC);
const MIXED = insert('▢⁄', 'Mixed number', '#?\\frac{#?}{#?}');
const MINUS = insert('−', 'Minus', '-');
const PLUS = insert('+', 'Plus', '+');
const POINT = insert('.', 'Decimal point', '.');
const POWER = insert('^', 'Power', '^{#?}');
const ROOT = insert('√', 'Square root', String.raw`\sqrt{#0}`);
const OPEN = insert('(', 'Open bracket', '(');
const CLOSE = insert(')', 'Close bracket', ')');

/**
 * Every profile's extra keys, beside the digits. `choice` has no keypad at all: its
 * answers are buttons. Each key emits only LaTeX the checker's parser reads; the
 * shared samples in testdata/keypad-samples.json pin that on both sides.
 */
const EXTRAS: Record<Exclude<KeypadProfile, 'choice'>, Key[]> = {
	numpad: [],
	numpad_neg: [MINUS],
	fraction: [FRACTION, LEFT, RIGHT],
	mixed: [MIXED, FRACTION_AFTER_WHOLE, LEFT, RIGHT],
	decimal: [POINT, MINUS],
	exponent: [POWER, ROOT, MINUS, OPEN, CLOSE, LEFT, RIGHT],
	algebra: [
		insert('x', 'x', 'x'),
		insert('y', 'y', 'y'),
		PLUS,
		MINUS,
		insert('=', 'Equals', '='),
		POWER,
		ROOT,
		OPEN,
		CLOSE,
		FRACTION,
		LEFT,
		RIGHT
	]
};

export interface KeypadLayout {
	/** Three-column block, row by row; the last key is delete. */
	digits: Key[];
	/** Profile-specific keys, shown beside the digits in a three-column block. */
	extras: Key[];
	go: Key;
}

/** The keypad for a profile, or null for `choice`, which has no keypad. */
export function layoutFor(profile: KeypadProfile): KeypadLayout | null {
	if (profile === 'choice') return null;
	return { digits: [...DIGITS, BACKSPACE], extras: EXTRAS[profile], go: GO };
}

/** Every key of a profile's keypad; none for `choice`. */
export function keysFor(profile: KeypadProfile): Key[] {
	const layout = layoutFor(profile);
	if (!layout) return [];
	return [...layout.digits, ...layout.extras, layout.go];
}

/**
 * Where the run of digits ending at `position` starts. `charBefore(i)` is the LaTeX of
 * the atom between offsets i - 1 and i. Returns `position` when no digit precedes it.
 */
export function numberStart(position: number, charBefore: (offset: number) => string): number {
	let start = position;
	while (start > 0 && /^[0-9]$/.test(charBefore(start))) start -= 1;
	return start;
}
