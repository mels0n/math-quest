import { ApiError } from '../../shared/api';

export const AUTH_COPY = {
	signup_word: "That secret word isn't right. Ask a grown-up for it.",
	nickname: 'Pick a nickname with 3 to 16 letters or numbers.',
	nickname_blocked: 'Please pick a different nickname.',
	nickname_taken: 'Someone already has that nickname. Try another.',
	pin: 'Your PIN needs exactly 4 numbers.',
	unauthorized: "That nickname and PIN don't match. Try again.",
	credential: "That didn't work. Check it and try again.",
	network: "Can't reach the game. Check your internet.",
	fallback: 'Something went wrong. Please try again.'
} as const;

function waitText(seconds: number): string {
	if (seconds < 90) return `${Math.max(1, seconds)} seconds`;
	return `${Math.ceil(seconds / 60)} minutes`;
}

/** Kid-facing text for a failed auth request. */
export function authErrorMessage(err: unknown): string {
	if (err instanceof ApiError) {
		if (err.status === 429) {
			return err.retryAfterS === null
				? 'Too many tries. Please wait a little and try again.'
				: `Too many tries. Please wait ${waitText(err.retryAfterS)} and try again.`;
		}
		if (err.code in AUTH_COPY && err.code !== 'fallback') {
			return AUTH_COPY[err.code as keyof typeof AUTH_COPY];
		}
	}
	return AUTH_COPY.fallback;
}
