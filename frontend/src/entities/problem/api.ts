import { apiFetch } from '../../shared/api';
import type { AnswerResult, Problem, Session } from './model';

export const startSession = () =>
	apiFetch<Session>('/api/play/sessions', { method: 'POST', body: { mode: 'adventure' } });

export const nextProblem = (sessionId: string) =>
	apiFetch<Problem>(`/api/play/sessions/${sessionId}/next`, { method: 'POST' });

export const submitAnswer = (problemId: string, latex: string) =>
	apiFetch<AnswerResult>(`/api/play/problems/${problemId}/answer`, {
		method: 'POST',
		body: { latex }
	});
