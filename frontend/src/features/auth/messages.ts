import { ApiError, commonErrorMessage } from '../../shared/api';
import type { AuthMode } from './auth-flow';

export const CODE_COPY = {
	signup_word: "That secret word isn't right. Ask a grown-up for it.",
	nickname: 'Pick a nickname with 3 to 16 letters or numbers.',
	nickname_blocked: 'Please pick a different nickname.',
	nickname_taken: 'Someone already has that nickname. Try another.',
	pin: 'Your PIN needs exactly 4 numbers.',
	unauthorized: "That nickname and PIN don't match. Try again.",
	credential: "That didn't work. Check it and try again."
} as const;

export const RECOVER_UNAUTHORIZED = "That nickname and recovery word don't match. Try again.";

/** Kid-facing text for a failed auth request. */
export function authErrorMessage(err: unknown, mode?: AuthMode): string {
	if (mode === 'recover' && err instanceof ApiError && err.status === 401) return RECOVER_UNAUTHORIZED;
	if (err instanceof ApiError && err.status !== 429 && Object.hasOwn(CODE_COPY, err.code)) {
		return CODE_COPY[err.code as keyof typeof CODE_COPY];
	}
	return commonErrorMessage(err);
}
