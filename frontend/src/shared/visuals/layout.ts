/**
 * Pure geometry for every visual: params in, a figure out. A figure is a viewBox size,
 * a screen-reader label and a list of plain shapes, so the Svelte components only draw
 * and every layout can be checked for fit without a browser. The SVG scales to its
 * container's width, so a figure fits any screen as long as its shapes stay inside
 * the viewBox (see `overflow`).
 */

import {
	PALETTE as C,
	type AlgebraTilesParams,
	type AreaModelParams,
	type ArrayParams,
	type BaseTenParams,
	type ClockParams,
	type FractionBarsParams,
	type MoneyParams,
	type NumberLineParams,
	type Visual
} from './model';

export type Shape =
	| { t: 'rect'; x: number; y: number; w: number; h: number; fill: string; stroke?: string; rx?: number }
	| { t: 'circle'; cx: number; cy: number; r: number; fill: string; stroke?: string }
	| { t: 'line'; x1: number; y1: number; x2: number; y2: number; stroke: string; width: number }
	| {
			t: 'path';
			d: string;
			stroke: string;
			width: number;
			/** The path's bounding box, for the fit check. */
			box: { x: number; y: number; w: number; h: number };
	  }
	| { t: 'poly'; points: [number, number][]; fill: string }
	| {
			t: 'text';
			x: number;
			y: number;
			text: string;
			size: number;
			fill: string;
			anchor: 'start' | 'middle' | 'end';
			bold?: boolean;
	  };

export interface Figure {
	width: number;
	height: number;
	/** What the picture shows, read by screen readers. */
	label: string;
	shapes: Shape[];
}

const STROKE = C.navy;
const plural = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;
const text = (
	x: number,
	y: number,
	value: string,
	size = 12,
	anchor: 'start' | 'middle' | 'end' = 'middle',
	fill: string = C.ink,
	bold = false
): Shape => ({ t: 'text', x, y, text: value, size, fill, anchor, bold });

// --- number line ---------------------------------------------------------------

export function jumpSizes(jumps: number | number[]): number[] {
	if (Array.isArray(jumps)) return jumps;
	return Array.from({ length: Math.abs(jumps) }, () => (jumps < 0 ? -1 : 1));
}

function labelStep(span: number): number {
	if (span <= 20) return 1;
	if (span <= 50) return 5;
	return 10;
}

export function numberLine(p: NumberLineParams): Figure {
	const steps = jumpSizes(p.jumps);
	const span = p.max - p.min;
	// A short line gets a narrower box, so it scales up and its numbers read larger.
	const width = span <= 10 ? 250 : 320;
	const margin = 14;
	const font = span <= 10 ? 14 : span <= 20 ? 13 : 11;
	// From 11 to 20 every number is labelled, every other one on a second row.
	const stagger = span > 10 && span <= 20;
	const unit = (width - 2 * margin) / span;
	const x = (v: number) => margin + (v - p.min) * unit;
	const biggest = steps.reduce((m, s) => Math.max(m, Math.abs(s)), 0);
	const arcTop = 6;
	const lineY = steps.length ? arcTop + Math.min(40, 14 + biggest * unit * 0.25) : 20;
	const height = lineY + 14 + font + (stagger ? font + 2 : 0);
	const shapes: Shape[] = [
		{ t: 'line', x1: margin, y1: lineY, x2: width - margin, y2: lineY, stroke: STROKE, width: 2 }
	];
	const every = labelStep(span);
	const tickEvery = span <= 50 ? 1 : 5;
	for (let v = p.min; v <= p.max; v += 1) {
		const labelled = (v - p.min) % every === 0 || v === p.max;
		if ((v - p.min) % tickEvery !== 0 && !labelled) continue;
		const tall = labelled ? 6 : 3;
		shapes.push({ t: 'line', x1: x(v), y1: lineY - tall, x2: x(v), y2: lineY + tall, stroke: STROKE, width: 1.5 });
		const row = stagger && (v - p.min) % 2 === 1 ? font + 2 : 0;
		if (labelled) shapes.push(text(x(v), lineY + 8 + font + row, String(v), font));
	}
	let at = p.start;
	if (at !== null) {
		for (const step of steps) {
			const from = x(at);
			const to = x(at + step);
			const rise = Math.min(lineY - arcTop, 12 + Math.abs(to - from) * 0.25);
			const mid = (from + to) / 2;
			const colour = step > 0 ? C.mint : C.berry;
			shapes.push({
				t: 'path',
				d: `M ${from} ${lineY} Q ${mid} ${lineY - 2 * rise} ${to} ${lineY}`,
				stroke: colour,
				width: 2.5,
				box: { x: Math.min(from, to), y: lineY - rise, w: Math.abs(to - from), h: rise }
			});
			const dir = step > 0 ? -1 : 1;
			shapes.push({
				t: 'poly',
				points: [
					[to, lineY - 1],
					[to + dir * 5, lineY - 7],
					[to + dir * 1, lineY - 8]
				],
				fill: colour
			});
			at += step;
		}
		shapes.push({ t: 'circle', cx: x(p.start as number), cy: lineY, r: 5, fill: C.navy });
	}
	if (p.end !== null) {
		shapes.push({ t: 'circle', cx: x(p.end), cy: lineY, r: 6, fill: C.gold, stroke: STROKE });
	}
	const parts = [`Number line from ${p.min} to ${p.max}.`];
	if (p.start !== null) parts.push(`Start at ${p.start}.`);
	if (steps.length) {
		const first = steps[0] ?? 1;
		if (steps.every((s) => s === first)) {
			const size = Math.abs(first);
			const way = first > 0 ? 'right' : 'left';
			parts.push(`${plural(steps.length, 'jump')} of ${size} to the ${way}.`);
		} else {
			parts.push(`Jumps of ${steps.map((s) => (s > 0 ? `${s} right` : `${-s} left`)).join(', then ')}.`);
		}
	}
	if (p.end !== null) parts.push(`Land on ${p.end}.`);
	return { width, height, label: parts.join(' '), shapes };
}

// --- base ten blocks ---------------------------------------------------------------

export function baseTen(p: BaseTenParams): Figure {
	const u = 8;
	const gap = 6;
	const pad = 4;
	const shapes: Shape[] = [];
	let left = pad;
	let tallest = 0;
	const cube = (cx: number, cy: number, w: number, h: number, fill: string) => {
		shapes.push({ t: 'rect', x: cx, y: cy, w, h, fill, stroke: STROKE });
	};
	if (p.hundreds > 0) {
		const cols = Math.min(p.hundreds, 5);
		for (let i = 0; i < p.hundreds; i += 1) {
			const cx = left + (i % cols) * (10 * u + gap);
			const cy = pad + Math.floor(i / cols) * (10 * u + gap);
			cube(cx, cy, 10 * u, 10 * u, C.gold);
			for (let k = 1; k < 10; k += 1) {
				shapes.push({ t: 'line', x1: cx + k * u, y1: cy, x2: cx + k * u, y2: cy + 10 * u, stroke: STROKE, width: 0.5 });
				shapes.push({ t: 'line', x1: cx, y1: cy + k * u, x2: cx + 10 * u, y2: cy + k * u, stroke: STROKE, width: 0.5 });
			}
		}
		left += cols * (10 * u + gap) + gap;
		tallest = Math.max(tallest, Math.ceil(p.hundreds / cols) * (10 * u + gap));
	}
	if (p.tens > 0) {
		const cols = Math.min(p.tens, 10);
		for (let i = 0; i < p.tens; i += 1) {
			const cx = left + (i % cols) * (u + gap);
			const cy = pad + Math.floor(i / cols) * (10 * u + gap);
			cube(cx, cy, u, 10 * u, C.mint);
			for (let k = 1; k < 10; k += 1) {
				shapes.push({ t: 'line', x1: cx, y1: cy + k * u, x2: cx + u, y2: cy + k * u, stroke: STROKE, width: 0.5 });
			}
		}
		left += cols * (u + gap) + gap;
		tallest = Math.max(tallest, Math.ceil(p.tens / cols) * (10 * u + gap));
	}
	if (p.ones > 0) {
		const size = 2 * u;
		const cols = 5;
		for (let i = 0; i < p.ones; i += 1) {
			const cx = left + (i % cols) * (size + 4);
			const cy = pad + Math.floor(i / cols) * (size + 4);
			cube(cx, cy, size, size, C.berry);
		}
		left += Math.min(p.ones, cols) * (size + 4);
		tallest = Math.max(tallest, Math.ceil(p.ones / cols) * (size + 4));
	}
	const parts = [];
	if (p.hundreds) parts.push(plural(p.hundreds, 'hundred'));
	if (p.tens) parts.push(plural(p.tens, 'ten'));
	if (p.ones) parts.push(plural(p.ones, 'one'));
	return {
		width: Math.max(left + pad, 40),
		height: tallest + 2 * pad,
		label: `Base ten blocks: ${parts.join(', ')}.`,
		shapes
	};
}

// --- fraction bars -----------------------------------------------------------------

export function fractionBars(p: FractionBarsParams): Figure {
	const width = 320;
	const barH = 30;
	const gap = 12;
	const labelW = 44;
	const left = labelW + 6;
	const right = width - 6;
	const shapes: Shape[] = [];
	p.bars.forEach((bar, i) => {
		const y = 6 + i * (barH + gap);
		const partW = (right - left) / bar.parts;
		for (let k = 0; k < bar.parts; k += 1) {
			shapes.push({
				t: 'rect',
				x: left + k * partW,
				y,
				w: partW,
				h: barH,
				fill: k < bar.shaded ? C.mint : C.paper,
				stroke: STROKE
			});
		}
		shapes.push(text(labelW / 2 + 4, y + barH / 2 + 5, `${bar.shaded}/${bar.parts}`, 14, 'middle', C.ink, true));
	});
	const label = p.bars.map((b) => `a bar in ${b.parts} parts with ${b.shaded} shaded`).join('; ');
	return {
		width,
		height: 12 + p.bars.length * barH + (p.bars.length - 1) * gap,
		label: `Fraction bars: ${label}.`,
		shapes
	};
}

// --- area model -------------------------------------------------------------------

/** Each part's share of `total`, but never under a quarter of an even share. */
function shares(parts: number[], total: number): number[] {
	const sum = parts.reduce((a, b) => a + b, 0);
	const floor = total / parts.length / 4;
	const raw = parts.map((v) => Math.max(floor, (v / sum) * total));
	const scale = total / raw.reduce((a, b) => a + b, 0);
	return raw.map((v) => v * scale);
}

export function areaModel(p: AreaModelParams): Figure {
	const width = 320;
	const top = 22;
	const left = 40;
	const gridW = width - left - 6;
	const gridH = 180;
	const colW = shares(p.cols, gridW);
	const rowH = shares(p.rows, gridH);
	const shapes: Shape[] = [];
	let y = top;
	p.rows.forEach((r, i) => {
		const h = rowH[i] ?? 0;
		let x = left;
		shapes.push(text(left / 2, y + h / 2 + 5, String(r), 13, 'middle', C.ink, true));
		p.cols.forEach((c, j) => {
			const w = colW[j] ?? 0;
			shapes.push({ t: 'rect', x, y, w, h, fill: (i + j) % 2 ? C.paper : '#e9fbf5', stroke: STROKE });
			if (p.show_products) {
				const size = Math.max(11, Math.min(14, w / 4));
				shapes.push(text(x + w / 2, y + h / 2 + size / 3, String(r * c), size));
			}
			x += w;
		});
		y += h;
	});
	let x = left;
	p.cols.forEach((c, j) => {
		const w = colW[j] ?? 0;
		shapes.push(text(x + w / 2, top - 7, String(c), 13, 'middle', C.ink, true));
		x += w;
	});
	const a = p.rows.join(' + ');
	const b = p.cols.join(' + ');
	return {
		width,
		height: top + gridH + 6,
		label: `Area model: ${a} by ${b}, split into ${p.rows.length * p.cols.length} parts.`,
		shapes
	};
}

// --- algebra tiles ----------------------------------------------------------------

export function algebraTiles(p: AlgebraTilesParams): Figure {
	const big = 44;
	const thin = 12;
	const gap = 5;
	const pad = 4;
	const shapes: Shape[] = [];
	let left = pad;
	let tallest = 0;
	const group = (count: number, w: number, h: number, positive: string, name: string, perRow: number) => {
		if (count === 0) return;
		const n = Math.abs(count);
		const cols = Math.min(n, perRow);
		for (let i = 0; i < n; i += 1) {
			const x = left + (i % cols) * (w + gap);
			const y = pad + Math.floor(i / cols) * (h + gap);
			shapes.push({ t: 'rect', x, y, w, h, fill: count > 0 ? positive : C.berry, stroke: STROKE, rx: 2 });
			if (w >= 20) shapes.push(text(x + w / 2, y + h / 2 + 5, count > 0 ? name : `-${name}`, 13));
		}
		left += cols * (w + gap) + 2 * gap;
		tallest = Math.max(tallest, Math.ceil(n / cols) * (h + gap));
	};
	group(p.x2, big, big, C.gold, 'x²', 4);
	group(p.x, thin, big, C.mint, 'x', 10);
	group(p.units, thin, thin, C.line, '1', 5);
	const parts = [];
	if (p.x2) parts.push(`${p.x2} x squared`);
	if (p.x) parts.push(`${p.x} x`);
	if (p.units) parts.push(`${p.units} ones`);
	return {
		width: Math.max(left - gap + pad, 40),
		height: tallest + 2 * pad,
		label: `Algebra tiles: ${parts.join(', ')}. Red tiles are negative.`,
		shapes
	};
}

// --- array ----------------------------------------------------------------------------

export function arrayGrid(p: ArrayParams): Figure {
	const cell = 24;
	const pad = 6;
	const shapes: Shape[] = [];
	for (let r = 0; r < p.rows; r += 1) {
		for (let c = 0; c < p.cols; c += 1) {
			shapes.push({ t: 'circle', cx: pad + c * cell + cell / 2, cy: pad + r * cell + cell / 2, r: 8, fill: C.mint, stroke: STROKE });
		}
	}
	return {
		width: 2 * pad + p.cols * cell,
		height: 2 * pad + p.rows * cell,
		label: `An array of ${plural(p.rows, 'row')} with ${p.cols} in each row.`,
		shapes
	};
}

// --- clock ----------------------------------------------------------------------------

export function clock(p: ClockParams): Figure {
	const size = 200;
	const c = size / 2;
	const r = 92;
	const shapes: Shape[] = [{ t: 'circle', cx: c, cy: c, r, fill: C.paper, stroke: STROKE }];
	for (let h = 1; h <= 12; h += 1) {
		const a = (h / 12) * 2 * Math.PI;
		shapes.push(text(c + Math.sin(a) * (r - 16), c - Math.cos(a) * (r - 16) + 5, String(h), 14, 'middle', C.ink, true));
	}
	for (let m = 0; m < 60; m += 5) {
		const a = (m / 60) * 2 * Math.PI;
		shapes.push({
			t: 'line',
			x1: c + Math.sin(a) * (r - 4),
			y1: c - Math.cos(a) * (r - 4),
			x2: c + Math.sin(a) * r,
			y2: c - Math.cos(a) * r,
			stroke: STROKE,
			width: 2
		});
	}
	const hand = (turns: number, length: number, colour: string, width: number) => {
		const a = turns * 2 * Math.PI;
		shapes.push({ t: 'line', x1: c, y1: c, x2: c + Math.sin(a) * length, y2: c - Math.cos(a) * length, stroke: colour, width });
	};
	hand(((p.hour % 12) + p.minute / 60) / 12, r * 0.5, C.navyDeep, 6);
	hand(p.minute / 60, r * 0.78, C.berry, 4);
	shapes.push({ t: 'circle', cx: c, cy: c, r: 5, fill: C.navyDeep });
	return {
		width: size,
		height: size,
		label: `A clock showing ${p.hour}:${String(p.minute).padStart(2, '0')}.`,
		shapes
	};
}

// --- money ---------------------------------------------------------------------------

const COINS = [
	{ key: 'quarters', one: 'quarter', r: 22, mark: '25¢', fill: C.line },
	{ key: 'dimes', one: 'dime', r: 16, mark: '10¢', fill: C.line },
	{ key: 'nickels', one: 'nickel', r: 19, mark: '5¢', fill: C.line },
	{ key: 'pennies', one: 'penny', r: 17, mark: '1¢', fill: C.gold }
] as const;

export function money(p: MoneyParams): Figure {
	const pad = 4;
	const gap = 6;
	const perRow = 300;
	const items: { w: number; h: number; draw: (x: number, y: number) => Shape[] }[] = [];
	for (let i = 0; i < p.dollars; i += 1) {
		items.push({
			w: 72,
			h: 36,
			draw: (x, y) => [
				{ t: 'rect', x, y, w: 72, h: 36, fill: C.mint, stroke: STROKE, rx: 3 },
				text(x + 36, y + 23, '$1', 15, 'middle', C.ink, true)
			]
		});
	}
	for (const coin of COINS) {
		for (let i = 0; i < p[coin.key]; i += 1) {
			items.push({
				w: 2 * coin.r,
				h: 2 * coin.r,
				draw: (x, y) => [
					{ t: 'circle', cx: x + coin.r, cy: y + coin.r, r: coin.r, fill: coin.fill, stroke: STROKE },
					text(x + coin.r, y + coin.r + 4, coin.mark, coin.r > 18 ? 12 : 10)
				]
			});
		}
	}
	const shapes: Shape[] = [];
	let x = pad;
	let y = pad;
	let rowH = 0;
	let widest = 0;
	for (const item of items) {
		if (x > pad && x + item.w > perRow) {
			x = pad;
			y += rowH + gap;
			rowH = 0;
		}
		shapes.push(...item.draw(x, y));
		x += item.w + gap;
		rowH = Math.max(rowH, item.h);
		widest = Math.max(widest, x - gap);
	}
	const parts: string[] = [];
	if (p.dollars) parts.push(plural(p.dollars, 'dollar bill'));
	for (const coin of COINS) {
		const n = p[coin.key];
		if (n) parts.push(plural(n, coin.one, coin.one === 'penny' ? 'pennies' : `${coin.one}s`));
	}
	return { width: widest + pad, height: y + rowH + pad, label: `Money: ${parts.join(', ')}.`, shapes };
}

// --- any visual -------------------------------------------------------------------

export function figure(visual: Visual): Figure {
	switch (visual.kind) {
		case 'number_line':
			return numberLine(visual.params);
		case 'base_ten':
			return baseTen(visual.params);
		case 'fraction_bars':
			return fractionBars(visual.params);
		case 'area_model':
			return areaModel(visual.params);
		case 'algebra_tiles':
			return algebraTiles(visual.params);
		case 'array':
			return arrayGrid(visual.params);
		case 'clock':
			return clock(visual.params);
		case 'money':
			return money(visual.params);
	}
}

/** Shapes that reach outside the figure's viewBox (empty when it fits). */
export function overflow(fig: Figure): Shape[] {
	const inside = (x0: number, y0: number, x1: number, y1: number) =>
		x0 >= -0.01 && y0 >= -0.01 && x1 <= fig.width + 0.01 && y1 <= fig.height + 0.01;
	return fig.shapes.filter((s) => {
		switch (s.t) {
			case 'rect':
				return !inside(s.x, s.y, s.x + s.w, s.y + s.h);
			case 'circle':
				return !inside(s.cx - s.r, s.cy - s.r, s.cx + s.r, s.cy + s.r);
			case 'line':
				return !inside(Math.min(s.x1, s.x2), Math.min(s.y1, s.y2), Math.max(s.x1, s.x2), Math.max(s.y1, s.y2));
			case 'path':
				return !inside(s.box.x, s.box.y, s.box.x + s.box.w, s.box.y + s.box.h);
			case 'poly': {
				const xs = s.points.map((p) => p[0]);
				const ys = s.points.map((p) => p[1]);
				return !inside(Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys));
			}
			case 'text': {
				const w = s.text.length * s.size * 0.62;
				const x0 = s.anchor === 'start' ? s.x : s.anchor === 'middle' ? s.x - w / 2 : s.x - w;
				return !inside(x0, s.y - s.size, x0 + w, s.y + s.size * 0.25);
			}
		}
	});
}
