import { apiFetch } from '../../shared/api';
import type { Answer, AnswerResult, Explanation, Hint, NextItem, Session } from './model';

export const startSession = () =>
	apiFetch<Session>('/api/play/sessions', { method: 'POST', body: { mode: 'adventure' } });

export const nextProblem = (sessionId: string) =>
	apiFetch<NextItem>(`/api/play/sessions/${sessionId}/next`, { method: 'POST' });

export const submitAnswer = (problemId: string, answer: Answer) =>
	apiFetch<AnswerResult>(`/api/play/problems/${problemId}/answer`, {
		method: 'POST',
		body: answer
	});

export const requestHint = (problemId: string) =>
	apiFetch<Hint>(`/api/play/problems/${problemId}/hint`, { method: 'POST' });

export const requestExplanation = (problemId: string) =>
	apiFetch<Explanation>(`/api/play/problems/${problemId}/explain`, { method: 'POST' });
