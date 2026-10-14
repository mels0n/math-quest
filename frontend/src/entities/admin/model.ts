import { ApiError, commonErrorMessage } from '../../shared/api';

export interface Done {
	ok: boolean;
}

export interface AdminPlayer {
	id: string;
	nickname: string;
	hidden: boolean;
	created_at: string;
	last_seen: string | null;
}

export interface PinReset {
	recovery_word: string;
}

export interface SignupWordState {
	set: boolean;
}

export interface ListParams {
	query?: string;
	offset?: number;
	limit?: number;
}

/** Delete stays disabled until the typed text equals the nickname exactly. */
export const canDelete = (nickname: string, typed: string): boolean =>
	nickname.length > 0 && typed === nickname;

export const isValidPin = (pin: string): boolean => /^[0-9]{4}$/.test(pin);

export const isValidSignupWord = (word: string): boolean => /^[A-Za-z]{3,32}$/.test(word);

export const NOT_ON_LAN = 'Admin is only available on the home network.';

const CODE_COPY: Record<string, string> = {
	unauthorized: 'That password is not right, or your session ended. Sign in again.',
	nickname_taken: 'Another player already has that nickname.',
	nickname_blocked: 'That nickname is not allowed. Try another.',
	not_found: 'That player no longer exists. Refresh the list.',
	invalid_request: 'Please check what you entered and try again.',
	csrf: 'The page is out of date. Reload it and try again.',
	busy: 'That player is busy right now. Try again in a moment.'
};

/** Plain-language text for a failed admin request; never shows the raw error code. */
export function adminErrorMessage(err: unknown): string {
	if (err instanceof ApiError && err.status !== 429 && Object.hasOwn(CODE_COPY, err.code)) {
		return CODE_COPY[err.code] as string;
	}
	return commonErrorMessage(err, 'Too many tries.');
}
