import { apiFetch } from '../../shared/api';
import type { Lesson, TryProblem, TryResult } from './lesson-model';

export const fetchLesson = (skillId: string) =>
	apiFetch<Lesson>(`/api/lessons/${encodeURIComponent(skillId)}`);

export const markLessonSeen = (skillId: string) =>
	apiFetch<{ skill_id: string; seen: boolean }>(
		`/api/lessons/${encodeURIComponent(skillId)}/seen`,
		{ method: 'POST' }
	);

export const startTry = (skillId: string) =>
	apiFetch<TryProblem>(`/api/lessons/${encodeURIComponent(skillId)}/try`, { method: 'POST' });

export const answerTry = (tryId: string, latex: string) =>
	apiFetch<TryResult>(`/api/lessons/tries/${encodeURIComponent(tryId)}/answer`, {
		method: 'POST',
		body: { latex }
	});
