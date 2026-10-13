import { describe, expect, it } from 'vitest';
import { ApiError, apiFetch } from '../../shared/api';
import { PLAY_COPY } from '../../entities/problem';
import { classifyPlayError } from './errors';

async function failWith(response: Response | Error): Promise<unknown> {
	const fetchImpl = (async () => {
		if (response instanceof Error) throw response;
		return response;
	}) as unknown as typeof fetch;
	return apiFetch('/api/x', { method: 'POST', fetchImpl }).catch((e: unknown) => e);
}

describe('classifyPlayError', () => {
	it('turns a 429 from the client into a kind wait message', async () => {
		const err = await failWith(
			Response.json({ error: 'rate_limited' }, { status: 429, headers: { 'Retry-After': '20' } })
		);
		expect(classifyPlayError(err)).toEqual({
			kind: 'notice',
			text: 'Whoa, slow down! Please wait 20 seconds and try again.'
		});
	});

	it('reports network and server failures as notices', async () => {
		expect(classifyPlayError(await failWith(new TypeError('offline')))).toMatchObject({
			kind: 'notice',
			text: expect.stringContaining('internet')
		});
		const server = await failWith(Response.json({ error: 'internal' }, { status: 500 }));
		expect(classifyPlayError(server)).toMatchObject({ kind: 'notice' });
	});

	it('signs out on 401 and reloads on problem_closed', () => {
		expect(classifyPlayError(new ApiError(401, 'unauthorized', null))).toEqual({
			kind: 'signed_out'
		});
		expect(classifyPlayError(new ApiError(409, 'problem_closed', null))).toEqual({
			kind: 'reload'
		});
	});

	it('has no em dashes in play copy', () => {
		for (const text of Object.values(PLAY_COPY)) expect(text).not.toContain('—');
	});
});
