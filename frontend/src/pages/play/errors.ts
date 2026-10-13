import { ApiError, commonErrorMessage } from '../../shared/api';
import { PLAY_COPY } from '../../entities/problem';

export type PlayFailure =
	| { kind: 'signed_out' }
	| { kind: 'reload' }
	| { kind: 'notice'; text: string };

/** What the play page should do about a failed request. */
export function classifyPlayError(err: unknown): PlayFailure {
	if (err instanceof ApiError) {
		if (err.status === 401) return { kind: 'signed_out' };
		if (err.code === 'problem_closed') return { kind: 'reload' };
	}
	return { kind: 'notice', text: commonErrorMessage(err, PLAY_COPY.rateLimited) };
}
