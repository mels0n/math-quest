/** Same-origin JSON fetch wrapper: adds the CSRF header and raises typed errors. */

const CSRF_HEADER = 'X-Requested-With';
const CSRF_VALUE = 'mathquest';

export class ApiError extends Error {
	readonly status: number;
	readonly code: string;
	readonly retryAfterS: number | null;

	constructor(status: number, code: string, retryAfterS: number | null) {
		super(code);
		this.name = 'ApiError';
		this.status = status;
		this.code = code;
		this.retryAfterS = retryAfterS;
	}
}

export interface ApiOptions {
	method?: 'GET' | 'POST';
	body?: unknown;
	fetchImpl?: typeof fetch;
}

function retryAfter(response: Response): number | null {
	const raw = response.headers.get('Retry-After');
	const seconds = raw === null ? Number.NaN : Number.parseInt(raw, 10);
	return Number.isFinite(seconds) && seconds >= 0 ? seconds : null;
}

async function errorCode(response: Response): Promise<string> {
	try {
		const data: unknown = await response.json();
		if (typeof data === 'object' && data !== null && 'error' in data) {
			const code = (data as { error: unknown }).error;
			if (typeof code === 'string') return code;
		}
	} catch {
		// Not JSON: fall through to the generic code.
	}
	return 'http_error';
}

export async function apiFetch<T>(path: string, options: ApiOptions = {}): Promise<T> {
	const { method = 'GET', body, fetchImpl = fetch } = options;
	const headers = new Headers({ [CSRF_HEADER]: CSRF_VALUE });
	const init: RequestInit = { method, headers, credentials: 'same-origin' };
	if (body !== undefined) {
		headers.set('Content-Type', 'application/json');
		init.body = JSON.stringify(body);
	}
	let response: Response;
	try {
		response = await fetchImpl(path, init);
	} catch {
		throw new ApiError(0, 'network', null);
	}
	if (!response.ok) {
		throw new ApiError(response.status, await errorCode(response), retryAfter(response));
	}
	return (await response.json()) as T;
}
