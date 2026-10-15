import { describe, expect, it } from 'vitest';
import { fetchMe } from './api';

describe('player api', () => {
	it('reads the player and the saved solved total from GET /api/me', async () => {
		const calls: { url: string; init: RequestInit }[] = [];
		const fetchImpl = (async (url: string, init: RequestInit) => {
			calls.push({ url, init });
			return Response.json({ player: { id: 'p1', nickname: 'SwiftOtter42' }, total_solved: 17 });
		}) as unknown as typeof fetch;

		const me = await fetchMe(fetchImpl);

		expect(calls[0]?.url).toBe('/api/me');
		expect(calls[0]?.init.method).toBe('GET');
		expect(me.player.nickname).toBe('SwiftOtter42');
		expect(me.total_solved).toBe(17);
	});
});
