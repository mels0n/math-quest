import { describe, expect, it } from 'vitest';
import { ApiError } from '../../shared/api';
import {
	adminErrorMessage,
	canDelete,
	coverageCell,
	isValidNickname,
	isValidPin,
	isValidSignupWord,
	parseSeed,
	resolveNotFound
} from './model';

describe('canDelete', () => {
	it('requires the exact nickname', () => {
		expect(canDelete('Sam_7', 'Sam_7')).toBe(true);
		expect(canDelete('Sam_7', 'sam_7')).toBe(false);
		expect(canDelete('Sam_7', 'Sam_7 ')).toBe(false);
		expect(canDelete('Sam_7', '')).toBe(false);
	});
});

describe('input validation', () => {
	it('accepts exactly 4 digits for a PIN', () => {
		expect(isValidPin('0420')).toBe(true);
		expect(isValidPin('123')).toBe(false);
		expect(isValidPin('12345')).toBe(false);
		expect(isValidPin('12a4')).toBe(false);
	});

	it('accepts 3 to 32 letters for a signup word', () => {
		expect(isValidSignupWord('abc')).toBe(true);
		expect(isValidSignupWord('ab')).toBe(false);
		expect(isValidSignupWord('ab1')).toBe(false);
		expect(isValidSignupWord('a'.repeat(33))).toBe(false);
	});
});

describe('adminErrorMessage', () => {
	const err = (status: number, code: string, retry: number | null = null) =>
		new ApiError(status, code, retry);

	it('maps known codes to plain copy without exposing the code', () => {
		expect(adminErrorMessage(err(401, 'unauthorized'))).toMatch(/password|sign in/i);
		expect(adminErrorMessage(err(409, 'nickname_taken'))).toMatch(/already/i);
		expect(adminErrorMessage(err(404, 'not_found'))).toMatch(/no longer|not found/i);
		expect(adminErrorMessage(err(422, 'invalid_request'))).toMatch(/check/i);
		expect(adminErrorMessage(err(403, 'csrf'))).toMatch(/reload/i);
		expect(adminErrorMessage(err(409, 'busy'))).toMatch(/busy|again/i);
	});

	it('shows the busy copy, not the kid copy, for a locked admin action', () => {
		const text = adminErrorMessage(err(429, 'locked', 30));
		expect(text).toMatch(/busy/i);
		expect(text).not.toMatch(/too many tries/i);
	});

	it('includes the wait time for rate limits', () => {
		expect(adminErrorMessage(err(429, 'rate_limited', 120))).toContain('2 minutes');
	});

	it('falls back for unknown failures and never leaks the raw code', () => {
		const text = adminErrorMessage(err(500, 'weird_code_x'));
		expect(text).not.toContain('weird_code_x');
		expect(adminErrorMessage(new Error('x'))).toBeTruthy();
	});
});

describe('nickname rules', () => {
	it('mirrors the backend pattern', () => {
		expect(isValidNickname('Sam_7')).toBe(true);
		expect(isValidNickname('a b-c')).toBe(true);
		expect(isValidNickname('ab')).toBe(false);
		expect(isValidNickname('a'.repeat(17))).toBe(false);
		expect(isValidNickname('bad!name')).toBe(false);
	});

	it('maps nickname and signup_word 422 codes to specific copy', () => {
		expect(adminErrorMessage(new ApiError(422, 'nickname', null))).toBe(
			'Use 3 to 16 letters, numbers, spaces, - or _.'
		);
		expect(adminErrorMessage(new ApiError(422, 'signup_word', null))).toBe(
			'Use 3 to 32 letters only.'
		);
	});
});

describe('resolveNotFound', () => {
	it('treats a still-valid session as a missing player', () => {
		expect(resolveNotFound(null)).toBe('missing');
	});

	it('treats a 404 session check as off-LAN and a 401 as signed out', () => {
		expect(resolveNotFound(new ApiError(404, 'not_found', null))).toBe('offlan');
		expect(resolveNotFound(new ApiError(401, 'unauthorized', null))).toBe('login');
	});

	it('leaves other failures undecided', () => {
		expect(resolveNotFound(new ApiError(500, 'http_error', null))).toBe('unknown');
		expect(resolveNotFound(new ApiError(0, 'network', null))).toBe('unknown');
		expect(resolveNotFound(new Error('x'))).toBe('unknown');
	});
});

describe('content preview helpers', () => {
	it('reads a seed: blank means the sample seeds, junk and huge numbers are refused', () => {
		expect(parseSeed('')).toBeUndefined();
		expect(parseSeed(' 42 ')).toBe(42);
		expect(parseSeed('0')).toBe(0);
		expect(parseSeed('2147483648')).toBe(2147483648);
		expect(parseSeed('9007199254740991')).toBe(9007199254740991);
		expect(parseSeed('9007199254740992')).toBeNull();
		expect(parseSeed('12345678901234567')).toBeNull();
		expect(parseSeed('-1')).toBeNull();
		expect(parseSeed('1e3')).toBeNull();
	});

	it('shows a coverage cell as have / target or n/a', () => {
		expect(coverageCell(15, '15+')).toBe('15 / 15+');
		expect(coverageCell(4, '3-4')).toBe('4 / 3-4');
		expect(coverageCell(null, '30+')).toBe('n/a');
		expect(coverageCell(1, undefined)).toBe('1 / ?');
	});
});
