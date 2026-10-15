import { apiFetch } from '../../shared/api';
import type {
	Answer,
	AnswerResult,
	Explanation,
	Hint,
	NextItem,
	PracticeTarget,
	Session,
	SkillList,
	Summary
} from './model';

export const startSession = () =>
	apiFetch<Session>('/api/play/sessions', { method: 'POST', body: { mode: 'adventure' } });

export const startPractice = (target: PracticeTarget) =>
	apiFetch<Session>('/api/play/sessions', {
		method: 'POST',
		body: { mode: 'practice', ...target }
	});

export const endSession = (sessionId: string) =>
	apiFetch<Summary>(`/api/play/sessions/${sessionId}/end`, { method: 'POST' });

export const fetchSkills = () => apiFetch<SkillList>('/api/skills');

/**
 * Tells `next` this client can show lessons (2) and session summaries (3). The server
 * offers each only to clients that send it, so a page loaded before them keeps getting
 * problems.
 */
export const CLIENT_HEADERS = { 'X-MathQuest-Client': '3' } as const;

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
