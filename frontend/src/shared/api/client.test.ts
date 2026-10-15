import { describe, expect, it } from 'vitest';
import { ApiError, apiFetch } from './client';

function recorder(response: Response) {
	const calls: { url: string; init: RequestInit }[] = [];
	const fetchImpl = (async (url: string, init: RequestInit) => {
		calls.push({ url, init });
		return response;
	}) as unknown as typeof fetch;
	return { calls, fetchImpl };
}

describe('apiFetch', () => {
	it('client adds X-Requested-With header', async () => {
		const { calls, fetchImpl } = recorder(Response.json({ ok: true }));
		await apiFetch('/api/auth/logout', { method: 'POST', fetchImpl });
		const headers = new Headers(calls[0]?.init.headers);
		expect(headers.get('X-Requested-With')).toBe('mathquest');
		expect(calls[0]?.init.credentials).toBe('same-origin');
	});

	it('adds extra headers but never lets them replace the CSRF header', async () => {
		const { calls, fetchImpl } = recorder(Response.json({ ok: true }));
		await apiFetch('/api/x', {
			method: 'POST',
			headers: { 'X-MathQuest-Client': '2', 'X-Requested-With': 'other' },
			fetchImpl
		});
		const headers = new Headers(calls[0]?.init.headers);
		expect(headers.get('X-MathQuest-Client')).toBe('2');
		expect(headers.get('X-Requested-With')).toBe('mathquest');
	});

	it('sends a JSON body with a content type', async () => {
		const { calls, fetchImpl } = recorder(Response.json({ ok: true }));
		await apiFetch('/api/x', { method: 'POST', body: { a: 1 }, fetchImpl });
		const headers = new Headers(calls[0]?.init.headers);
		expect(headers.get('Content-Type')).toBe('application/json');
		expect(calls[0]?.init.body).toBe('{"a":1}');
	});

	it('throws a typed error with code, status and retry-after', async () => {
		const { fetchImpl } = recorder(
			Response.json({ error: 'locked' }, { status: 429, headers: { 'Retry-After': '30' } })
		);
		const err = await apiFetch('/api/x', { method: 'POST', fetchImpl }).catch((e: unknown) => e);
		expect(err).toBeInstanceOf(ApiError);
		expect(err).toMatchObject({ status: 429, code: 'locked', retryAfterS: 30 });
	});

	it('falls back to a generic code when the body is not JSON', async () => {
		const { fetchImpl } = recorder(new Response('boom', { status: 502 }));
		const err = await apiFetch('/api/x', { fetchImpl }).catch((e: unknown) => e);
		expect(err).toMatchObject({ status: 502, code: 'http_error' });
	});
});
