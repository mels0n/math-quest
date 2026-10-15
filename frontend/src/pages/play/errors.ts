import { ApiError, commonErrorMessage } from '../../shared/api';
import { PLAY_COPY } from '../../entities/problem';

export type PlayFailure =
	| { kind: 'signed_out' }
	| { kind: 'reload' }
	| { kind: 'ignore' }
	| { kind: 'notice'; text: string };

const IGNORED = new Set(['problem_scored', 'no_more_hints', 'explain_after_a_try']);

/** What the play page should do about a failed request. */
export function classifyPlayError(err: unknown): PlayFailure {
	if (err instanceof ApiError) {
		if (err.status === 401) return { kind: 'signed_out' };
		if (err.code === 'problem_closed') return { kind: 'reload' };
		// Help asked for on a problem already scored, or past its last hint or before a
		// miss: nothing to show, nothing went wrong.
		if (IGNORED.has(err.code)) return { kind: 'ignore' };
	}
	return { kind: 'notice', text: commonErrorMessage(err, PLAY_COPY.rateLimited) };
}
