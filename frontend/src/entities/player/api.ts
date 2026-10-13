import { apiFetch } from '../../shared/api';
import type { PlayerEnvelope, PlayerWithRecovery } from './model';

export const fetchMe = () => apiFetch<PlayerEnvelope>('/api/me');

export const suggestNickname = () =>
	apiFetch<{ nickname: string }>('/api/auth/nickname-suggestion').then((r) => r.nickname);

export const signup = (signupWord: string, nickname: string, pin: string) =>
	apiFetch<PlayerWithRecovery>('/api/auth/signup', {
		method: 'POST',
		body: { signup_word: signupWord, nickname, pin }
	});

export const login = (nickname: string, pin: string) =>
	apiFetch<PlayerEnvelope>('/api/auth/login', { method: 'POST', body: { nickname, pin } });

export const recover = (nickname: string, recoveryWord: string, newPin: string) =>
	apiFetch<PlayerWithRecovery>('/api/auth/recover', {
		method: 'POST',
		body: { nickname, recovery_word: recoveryWord, new_pin: newPin }
	});

export const logout = () => apiFetch<{ ok: boolean }>('/api/auth/logout', { method: 'POST' });
