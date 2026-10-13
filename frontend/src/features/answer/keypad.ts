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

const PROFILES: Record<KeypadProfile, Key[]> = {
	numbers: [...DIGITS, BACKSPACE, GO],
	fractions: [...DIGITS, FRACTION, LEFT, RIGHT, BACKSPACE, GO],
	algebra: [
		...DIGITS,
		insert('x', 'x', 'x'),
		insert('+', 'Plus', '+'),
		insert('−', 'Minus', '-'),
		insert('=', 'Equals', '='),
		insert('^', 'Power', '^{#?}'),
		insert('√', 'Square root', '\\sqrt{#0}'),
		insert('(', 'Open bracket', '('),
		insert(')', 'Close bracket', ')'),
		FRACTION,
		LEFT,
		RIGHT,
		BACKSPACE,
		GO
	]
};

export function keysFor(profile: KeypadProfile): Key[] {
	return PROFILES[profile];
}
