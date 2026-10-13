import { ApiError } from './client';

export const ERROR_COPY = {
	network: "Can't reach the game. Check your internet.",
	fallback: 'Something went wrong. Please try again.',
	slowDown: 'Whoa, slow down! Please wait a little and try again.'
} as const;

export function waitText(seconds: number): string {
	if (seconds < 90) return `${Math.max(1, seconds)} seconds`;
	return `${Math.ceil(seconds / 60)} minutes`;
}

/** Kid-facing text for the failures every request can have (rate limit, network, anything else). */
export function commonErrorMessage(err: unknown, rateLimited = 'Too many tries.'): string {
	if (err instanceof ApiError) {
		if (err.status === 429) {
			return err.retryAfterS === null
				? `${rateLimited} Please wait a little and try again.`
				: `${rateLimited} Please wait ${waitText(err.retryAfterS)} and try again.`;
		}
		if (err.code === 'network') return ERROR_COPY.network;
	}
	return ERROR_COPY.fallback;
}
