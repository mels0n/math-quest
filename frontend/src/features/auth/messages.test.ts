import { describe, expect, it } from 'vitest';
import { ApiError } from '../../shared/api';
import { ERROR_COPY } from '../../shared/api';
import { CODE_COPY, RECOVER_UNAUTHORIZED, authErrorMessage } from './messages';

describe('authErrorMessage', () => {
	it('maps known codes and lockouts', () => {
		expect(authErrorMessage(new ApiError(409, 'nickname_taken', null))).toMatch(/already/);
		expect(authErrorMessage(new ApiError(429, 'locked', 1800))).toMatch(/30 minutes/);
		expect(authErrorMessage(new ApiError(429, 'rate_limited', 20))).toMatch(/20 seconds/);
		expect(authErrorMessage(new Error('x'))).toBe(ERROR_COPY.fallback);
	});

	it('names the recovery word when recovery fails', () => {
		const err = new ApiError(401, 'unauthorized', null);
		expect(authErrorMessage(err, 'recover')).toBe(RECOVER_UNAUTHORIZED);
		expect(authErrorMessage(err, 'recover')).toMatch(/recovery word/);
		expect(authErrorMessage(err, 'login')).toMatch(/nickname and PIN/);
		expect(authErrorMessage(err)).toMatch(/nickname and PIN/);
		expect(authErrorMessage(new ApiError(429, 'locked', 1800), 'recover')).toMatch(/30 minutes/);
	});

	it('has no em dashes in any copy', () => {
		for (const text of [RECOVER_UNAUTHORIZED, ...Object.values(CODE_COPY), ...Object.values(ERROR_COPY)]) expect(text).not.toContain('—');
	});
});
