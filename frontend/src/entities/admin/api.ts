import { apiFetch } from '../../shared/api';
import type {
	AdminPlayer,
	ContentOverview,
	Done,
	ListParams,
	PinReset,
	PreviewParams,
	SignupWordState,
	SkillPreview
} from './model';

type Impl = typeof fetch | undefined;

const base = '/api/admin';
const playerPath = (id: string) => `${base}/players/${encodeURIComponent(id)}`;

export const adminMe = (fetchImpl?: Impl) => apiFetch<Done>(`${base}/me`, { fetchImpl });

export const adminLogin = (password: string, fetchImpl?: Impl) =>
	apiFetch<Done>(`${base}/login`, {
		method: 'POST',
		body: { password },
		fetchImpl
	});

export const adminLogout = (fetchImpl?: Impl) =>
	apiFetch<Done>(`${base}/logout`, { method: 'POST', fetchImpl });

export function listPlayers(params: ListParams, fetchImpl?: Impl): Promise<AdminPlayer[]> {
	const search = new URLSearchParams();
	if (params.query) search.set('query', params.query);
	if (params.offset !== undefined) search.set('offset', String(params.offset));
	if (params.limit !== undefined) search.set('limit', String(params.limit));
	const qs = search.toString();
	return apiFetch<AdminPlayer[]>(`${base}/players${qs ? `?${qs}` : ''}`, {
		fetchImpl
	});
}

export const hidePlayer = (id: string, fetchImpl?: Impl) =>
	apiFetch<Done>(`${playerPath(id)}/hide`, { method: 'POST', fetchImpl });

export const unhidePlayer = (id: string, fetchImpl?: Impl) =>
	apiFetch<Done>(`${playerPath(id)}/unhide`, { method: 'POST', fetchImpl });

export const renamePlayer = (id: string, nickname: string, fetchImpl?: Impl) =>
	apiFetch<Done>(`${playerPath(id)}/rename`, {
		method: 'POST',
		body: { nickname },
		fetchImpl
	});

export const resetPin = (id: string, pin: string, fetchImpl?: Impl) =>
	apiFetch<PinReset>(`${playerPath(id)}/reset-pin`, {
		method: 'POST',
		body: { pin },
		fetchImpl
	});

export const deletePlayer = (id: string, fetchImpl?: Impl) =>
	apiFetch<Done>(playerPath(id), { method: 'DELETE', fetchImpl });

export const signupWordState = (fetchImpl?: Impl) =>
	apiFetch<SignupWordState>(`${base}/signup-word`, { fetchImpl });

export const setSignupWord = (word: string, fetchImpl?: Impl) =>
	apiFetch<Done>(`${base}/signup-word`, {
		method: 'PUT',
		body: { word },
		fetchImpl
	});

export const getContent = (fetchImpl?: Impl) =>
	apiFetch<ContentOverview>(`${base}/content`, { fetchImpl });

export function getSkillPreview(
	skillId: string,
	params: PreviewParams,
	fetchImpl?: Impl
): Promise<SkillPreview> {
	const search = new URLSearchParams();
	if (params.seed !== undefined) search.set('seed', String(params.seed));
	if (params.tier !== undefined) search.set('tier', String(params.tier));
	const qs = search.toString();
	const path = `${base}/content/skills/${encodeURIComponent(skillId)}`;
	return apiFetch<SkillPreview>(`${path}${qs ? `?${qs}` : ''}`, { fetchImpl });
}

/**
 * Where to download the stuck log: problems learners stayed stuck on after every
 * explanation, as JSON (the file `content-report --stuck` reads) or CSV. No player names.
 */
export function stuckLogUrl(format: 'json' | 'csv'): string {
	return format === 'csv' ? `${base}/stuck-log?format=csv` : `${base}/stuck-log`;
}
