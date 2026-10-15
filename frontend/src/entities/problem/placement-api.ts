import { apiFetch } from '../../shared/api';
import type { Answer } from './model';
import type { GradeHint, PlacementResult, PlacementStep } from './placement-model';

/** Starts a placement round (a retake ends any unfinished one). */
export const startPlacement = (gradeHint: GradeHint | null) =>
	apiFetch<PlacementStep>('/api/placement/start', {
		method: 'POST',
		body: gradeHint === null ? {} : { grade_hint: gradeHint }
	});

export const answerPlacement = (placementId: string, problemId: string, answer: Answer) =>
	apiFetch<PlacementResult>('/api/placement/answer', {
		method: 'POST',
		body: { placement_id: placementId, problem_id: problemId, ...answer }
	});
