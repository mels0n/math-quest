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

/** Mirrors the backend nickname rule: 3 to 16 of letters, numbers, space, underscore, hyphen. */
export const isValidNickname = (nickname: string): boolean => /^[A-Za-z0-9 _-]{3,16}$/.test(nickname);

export const isValidSignupWord = (word: string): boolean => /^[A-Za-z]{3,32}$/.test(word);

export const NOT_ON_LAN = 'Admin is only available on the home network.';

const CODE_COPY: Record<string, string> = {
	unauthorized: 'That password is not right, or your session ended. Sign in again.',
	nickname_taken: 'Another player already has that nickname.',
	nickname: 'Use 3 to 16 letters, numbers, spaces, - or _.',
	signup_word: 'Use 3 to 32 letters only.',
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

export type NotFoundVerdict = 'offlan' | 'login' | 'missing' | 'unknown';

/**
 * The backend answers 404 both for an off-LAN client and for an unknown player. After a 404 from
 * a player action, the result of a follow-up session check (null when it succeeded) tells which.
 */
export function resolveNotFound(sessionCheckFailure: unknown): NotFoundVerdict {
	if (sessionCheckFailure === null) return 'missing';
	if (sessionCheckFailure instanceof ApiError) {
		if (sessionCheckFailure.status === 404) return 'offlan';
		if (sessionCheckFailure.status === 401) return 'login';
	}
	return 'unknown';
}
