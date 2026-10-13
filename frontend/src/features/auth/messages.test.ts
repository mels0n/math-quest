import { describe, expect, it } from 'vitest';
import { ApiError } from '../../shared/api';
import { AUTH_COPY, authErrorMessage } from './messages';

describe('authErrorMessage', () => {
	it('maps known codes and lockouts', () => {
		expect(authErrorMessage(new ApiError(409, 'nickname_taken', null))).toMatch(/already/);
		expect(authErrorMessage(new ApiError(429, 'locked', 1800))).toMatch(/30 minutes/);
		expect(authErrorMessage(new ApiError(429, 'rate_limited', 20))).toMatch(/20 seconds/);
		expect(authErrorMessage(new Error('x'))).toBe(AUTH_COPY.fallback);
	});

	it('has no em dashes in any copy', () => {
		for (const text of Object.values(AUTH_COPY)) expect(text).not.toContain('—');
	});
});
