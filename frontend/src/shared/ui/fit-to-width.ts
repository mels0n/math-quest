/**
 * Shrinks math runs that are wider than their container so a long expression fits
 * the card instead of scrolling sideways. Text runs wrap on their own.
 */

/** Smallest font scale a math run is shrunk to. */
export const MIN_SCALE = 0.25;

/** Pixels kept free when shrinking, so sub-pixel layout rounding cannot overflow. */
const SLACK_PX = 2;

/** Extra shrink steps tried, each this much smaller, when a shrunk run is still too wide. */
const MAX_EXTRA_STEPS = 6;
const EXTRA_STEP = 0.02;

/** Font scale (at most 1) that makes content of `contentWidth` fit `available`. */
export function fitScale(contentWidth: number, available: number, min = MIN_SCALE): number {
	if (!(contentWidth > 0) || !(available > 0) || contentWidth <= available) return 1;
	// Round down so rounding never leaves the run a fraction of a pixel too wide.
	return Math.max(min, Math.floor((available / contentWidth) * 1000) / 1000);
}

/** The parts of a DOM element the fit needs, so it can be tested without a browser. */
export interface FitRun {
	style: { fontSize: string };
	scrollWidth: number;
	getBoundingClientRect(): { width: number };
}

export interface FitContainer {
	clientWidth: number;
	querySelectorAll(selector: string): Iterable<FitRun>;
}

/** Class a prompt's math runs carry; the fit finds them by it. */
export const MATH_RUN_CLASS = 'math-run';
export const MATH_RUN_SELECTOR = `.${MATH_RUN_CLASS}`;

/**
 * Measures every math run at full size and shrinks the ones wider than the container.
 * The container must have no horizontal padding: its clientWidth is the space a run has.
 */
export function fitRuns(container: FitContainer): void {
	const available = container.clientWidth;
	const runs = [...container.querySelectorAll(MATH_RUN_SELECTOR)];
	// Reset, then read every width, then write every size: one layout, no thrashing. Only the
	// bounded verify pass below reads again after writing, and only for runs that shrank.
	for (const run of runs) run.style.fontSize = '';
	const widths = runs.map((run) => Math.max(run.getBoundingClientRect().width, run.scrollWidth));
	const scales = runs.map((run, i) => {
		const width = widths[i] as number;
		const scale = width > available ? fitScale(width, available - SLACK_PX) : 1;
		if (scale < 1) run.style.fontSize = `${scale}em`;
		return scale;
	});
	// Glyph advances are rounded to whole pixels on some platforms, so a small shrink can
	// leave a run a few pixels too wide. Check the shrunk runs (against the full width, no slack) and step them down further.
	runs.forEach((run, i) => {
		let scale = scales[i] as number;
		for (let step = 0; step < MAX_EXTRA_STEPS && scale < 1 && scale > MIN_SCALE; step++) {
			if (Math.max(run.getBoundingClientRect().width, run.scrollWidth) <= available) break;
			scale = Math.max(MIN_SCALE, Math.floor((scale - EXTRA_STEP) * 1000) / 1000);
			run.style.fontSize = `${scale}em`;
		}
	});
}

/**
 * Fits now, again whenever the container is resized and once web fonts have loaded.
 * Returns a function that stops watching. Without ResizeObserver (very old browsers)
 * it fits once and on window resize.
 */
export function watchFit(container: HTMLElement): () => void {
	let stopped = false;
	const fit = () => {
		if (!stopped && container.isConnected) fitRuns(container);
	};
	fit();
	void document.fonts?.ready.then(fit);
	if (typeof ResizeObserver !== 'undefined') {
		let lastWidth = container.clientWidth;
		const observer = new ResizeObserver(() => {
			// Only a width change can change the fit; shrinking a run changes the height.
			if (container.clientWidth === lastWidth) return;
			lastWidth = container.clientWidth;
			fit();
		});
		observer.observe(container);
		return () => {
			stopped = true;
			observer.disconnect();
		};
	}
	window.addEventListener('resize', fit);
	return () => {
		stopped = true;
		window.removeEventListener('resize', fit);
	};
}
