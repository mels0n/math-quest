import { describe, expect, it } from 'vitest';
import * as admin from './api';

function recorder(body: unknown = { ok: true }) {
	const calls: { url: string; init: RequestInit }[] = [];
	const fetchImpl = (async (url: string, init: RequestInit) => {
		calls.push({ url, init });
		return Response.json(body);
	}) as unknown as typeof fetch;
	return { calls, fetchImpl };
}

const ID = '3f2c1d9e-0000-4000-8000-000000000001';

describe('admin api', () => {
	it('checks the session with GET /api/admin/me and the CSRF header', async () => {
		const { calls, fetchImpl } = recorder();
		await admin.adminMe(fetchImpl);
		expect(calls[0]?.url).toBe('/api/admin/me');
		expect(calls[0]?.init.method).toBe('GET');
		expect(new Headers(calls[0]?.init.headers).get('X-Requested-With')).toBe('mathquest');
	});

	it('logs in and out with POST', async () => {
		const { calls, fetchImpl } = recorder();
		await admin.adminLogin('pw', fetchImpl);
		await admin.adminLogout(fetchImpl);
		expect(calls[0]).toMatchObject({ url: '/api/admin/login', init: { method: 'POST' } });
		expect(calls[0]?.init.body).toBe('{"password":"pw"}');
		expect(calls[1]).toMatchObject({ url: '/api/admin/logout', init: { method: 'POST' } });
	});

	it('lists players with an encoded query, offset and limit', async () => {
		const { calls, fetchImpl } = recorder([]);
		await admin.listPlayers({ query: 'a b&c', offset: 50, limit: 25 }, fetchImpl);
		expect(calls[0]?.url).toBe('/api/admin/players?query=a+b%26c&offset=50&limit=25');
		await admin.listPlayers({}, fetchImpl);
		expect(calls[1]?.url).toBe('/api/admin/players');
	});

	it('hides, unhides, renames and deletes by player id', async () => {
		const { calls, fetchImpl } = recorder();
		await admin.hidePlayer(ID, fetchImpl);
		await admin.unhidePlayer(ID, fetchImpl);
		await admin.renamePlayer(ID, 'New Name', fetchImpl);
		await admin.deletePlayer(ID, fetchImpl);
		expect(calls.map((c) => [c.init.method, c.url])).toEqual([
			['POST', `/api/admin/players/${ID}/hide`],
			['POST', `/api/admin/players/${ID}/unhide`],
			['POST', `/api/admin/players/${ID}/rename`],
			['DELETE', `/api/admin/players/${ID}`]
		]);
		expect(calls[2]?.init.body).toBe('{"nickname":"New Name"}');
	});

	it('resets a PIN and returns the recovery word', async () => {
		const { calls, fetchImpl } = recorder({ recovery_word: 'maple' });
		const result = await admin.resetPin(ID, '1234', fetchImpl);
		expect(calls[0]).toMatchObject({
			url: `/api/admin/players/${ID}/reset-pin`,
			init: { method: 'POST', body: '{"pin":"1234"}' }
		});
		expect(result.recovery_word).toBe('maple');
	});

	it('reads and sets the signup word', async () => {
		const { calls, fetchImpl } = recorder({ set: true });
		await admin.signupWordState(fetchImpl);
		await admin.setSignupWord('tiger', fetchImpl);
		expect(calls[0]).toMatchObject({ url: '/api/admin/signup-word', init: { method: 'GET' } });
		expect(calls[1]).toMatchObject({
			url: '/api/admin/signup-word',
			init: { method: 'PUT', body: '{"word":"tiger"}' }
		});
	});
});
