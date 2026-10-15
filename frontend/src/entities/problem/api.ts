import { apiFetch } from '../../shared/api';
import type { Answer, AnswerResult, Explanation, Hint, NextItem, Session } from './model';

export const startSession = () =>
	apiFetch<Session>('/api/play/sessions', { method: 'POST', body: { mode: 'adventure' } });

/**
 * Tells `next` this client can show lessons. The server offers a lesson only to clients
 * that send it, so a page loaded before lessons existed keeps getting problems.
 */
export const CLIENT_HEADERS = { 'X-MathQuest-Client': '2' } as const;

export const nextProblem = (sessionId: string) =>
	apiFetch<NextItem>(`/api/play/sessions/${sessionId}/next`, {
		method: 'POST',
		headers: CLIENT_HEADERS
	});

export const submitAnswer = (problemId: string, answer: Answer) =>
	apiFetch<AnswerResult>(`/api/play/problems/${problemId}/answer`, {
		method: 'POST',
		body: answer
	});

export const requestHint = (problemId: string) =>
	apiFetch<Hint>(`/api/play/problems/${problemId}/hint`, { method: 'POST' });

export const requestExplanation = (problemId: string) =>
	apiFetch<Explanation>(`/api/play/problems/${problemId}/explain`, { method: 'POST' });
