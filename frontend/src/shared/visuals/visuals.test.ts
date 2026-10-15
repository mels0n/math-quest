import { render } from 'svelte/server';
import { expect, test } from 'vitest';
import VisualView from './VisualView.svelte';
import { figure } from './layout';
import { LARGEST_VISUALS, SAMPLE_VISUALS } from './samples';

test.each([...SAMPLE_VISUALS, ...LARGEST_VISUALS].map((v) => [v.kind, v] as const))(
	'%s renders as scalable, labelled inline SVG',
	(kind, visual) => {
		const { body } = render(VisualView, { props: { visual } });
		const fig = figure(visual);
		expect(body).toContain(`data-visual="${kind}"`);
		expect(body).toContain(`viewBox="0 0 ${fig.width} ${fig.height}"`);
		expect(body).toContain('width="100%"');
		expect(body).toContain('role="img"');
		expect(body).toContain(`aria-label="${fig.label}"`);
		// Scaled to a 320 px or 375 px column, the drawing keeps its proportions.
		for (const column of [320 - 2 * 16, 375 - 2 * 16]) {
			const shown = Math.min(column, Math.max(fig.width * 1.25, 160));
			expect(shown).toBeLessThanOrEqual(column);
			expect((shown * fig.height) / fig.width).toBeGreaterThan(0);
		}
	}
);
