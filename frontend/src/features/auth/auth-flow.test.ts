import { describe, expect, it, vi } from 'vitest';
import { createRecoveryReveal, submitAuth, type AuthApi } from './auth-flow';

const player = { id: 'p1', nickname: 'GreatHeron91' };
const fields = { nickname: ' GreatHeron91 ', pin: '1234', signupWord: '', recoveryWord: ' old-word ' };

function fakeApi(): AuthApi {
	return {
		login: vi.fn(async () => ({ player })),
		signup: vi.fn(async () => ({ player, recovery_word: 'first-word' })),
		recover: vi.fn(async () => ({ player, recovery_word: 'new-word' }))
	};
}

describe('submitAuth', () => {
	it('recover returns the NEW recovery word and trims inputs', async () => {
		const api = fakeApi();
		const outcome = await submitAuth('recover', fields, api);
		expect(outcome).toEqual({ kind: 'reveal', word: 'new-word', player });
		expect(api.recover).toHaveBeenCalledWith('GreatHeron91', 'old-word', '1234');
	});

	it('login signs in directly without a reveal', async () => {
		expect(await submitAuth('login', fields, fakeApi())).toEqual({ kind: 'signed_in', player });
	});
});

describe('createRecoveryReveal', () => {
	it('shows the word once and signs in only after "I wrote it down"', () => {
		const onSignedIn = vi.fn();
		const reveal = createRecoveryReveal({ word: 'new-word', player }, onSignedIn);
		expect(reveal.word()).toBe('new-word');
		expect(onSignedIn).not.toHaveBeenCalled();
		reveal.acknowledge();
		reveal.acknowledge();
		expect(onSignedIn).toHaveBeenCalledTimes(1);
		expect(onSignedIn).toHaveBeenCalledWith(player);
		expect(reveal.word()).toBeNull();
	});
});
