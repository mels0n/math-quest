import type { KeypadProfile } from '../../entities/problem';

export type KeyAction =
	| { kind: 'insert'; latex: string }
	| { kind: 'command'; command: 'deleteBackward' | 'moveToPreviousChar' | 'moveToNextChar' }
	| { kind: 'go' };

export interface Key {
	label: string;
	name: string;
	action: KeyAction;
	tone?: 'gold' | 'mint' | 'aux';
}

const digit = (d: string): Key => ({ label: d, name: d, action: { kind: 'insert', latex: d } });
const insert = (label: string, name: string, latex: string): Key => ({
	label,
	name,
	action: { kind: 'insert', latex },
	tone: 'aux'
});

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

const FRACTION = insert('⁄', 'Fraction', '\\frac{#0}{#?}');
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
	mixed: [MIXED, FRACTION, LEFT, RIGHT],
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
