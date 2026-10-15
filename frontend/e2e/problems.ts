import type { APIResponse, Page, Route } from '@playwright/test';

const CSRF = { 'X-Requested-With': 'mathquest' };

/**
 * Fetches the real next problem for an intercepted `next` request. A lesson due first
 * is marked seen and the request repeated, so specs about the problem card get a problem.
 */
export async function fetchProblem(
	page: Page,
	route: Route
): Promise<{ response: APIResponse; body: Record<string, unknown> }> {
	for (;;) {
		const response = await route.fetch();
		const body = (await response.json()) as Record<string, unknown>;
		if (body.type !== 'lesson') return { response, body };
		const seen = await page.request.post(`/api/lessons/${String(body.skill_id)}/seen`, {
			headers: CSRF
		});
		if (!seen.ok()) throw new Error(`could not mark the lesson seen: ${seen.status()}`);
	}
}
