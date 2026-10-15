/**
 * A tiny, safe reader for the Markdown used in content bodies.
 *
 * Content bodies arrive as prompt parts: text (which may hold Markdown) and math (LaTeX).
 * Only paragraphs, bulleted and numbered lists, **bold** and *italic* (or _italic_) are
 * understood; everything else stays literal text. The result is plain data, rendered
 * with text nodes, so no input is ever interpreted as HTML.
 */

export interface RichPart {
	kind: 'text' | 'math';
	value: string;
}

export interface Inline {
	kind: 'text' | 'math';
	value: string;
	bold: boolean;
	italic: boolean;
}

export type Block =
	| { kind: 'p'; inlines: Inline[] }
	| { kind: 'ul'; items: Inline[][] }
	| { kind: 'ol'; start: number; items: Inline[][] };

/** Stands in for a math part while text is scanned; never typed by authors. */
const MATH = '\uE000';
const ORDERED = /^\s*(\d+)[.)]\s+/;
const BULLET = /^\s*[-*]\s+(?!\*)/;

type Line = { text: string; math: string[] };

function lines(parts: readonly RichPart[]): Line[] {
	const out: Line[] = [{ text: '', math: [] }];
	for (const part of parts) {
		const current = () => out[out.length - 1] as Line;
		if (part.kind === 'math') {
			current().text += MATH;
			current().math.push(part.value);
			continue;
		}
		const pieces = part.value.replaceAll(MATH, '').split('\n');
		pieces.forEach((piece, i) => {
			if (i > 0) out.push({ text: '', math: [] });
			current().text += piece;
		});
	}
	return out;
}

/** Text with emphasis markers resolved into runs; math placeholders kept in place. */
function emphasis(text: string): { value: string; bold: boolean; italic: boolean }[] {
	const out: { value: string; bold: boolean; italic: boolean }[] = [];
	const pattern = /\*\*(.+?)\*\*|\*(?!\s)(.+?)\*|(?<![A-Za-z0-9])_(?!\s)(.+?)_(?![A-Za-z0-9])/g;
	let at = 0;
	for (const match of text.matchAll(pattern)) {
		if (match.index > at)
			out.push({
				value: text.slice(at, match.index),
				bold: false,
				italic: false
			});
		if (match[1] !== undefined) {
			for (const run of emphasis(match[1])) out.push({ ...run, bold: true });
		} else {
			out.push({
				value: match[2] ?? match[3] ?? '',
				bold: false,
				italic: true
			});
		}
		at = match.index + match[0].length;
	}
	if (at < text.length) out.push({ value: text.slice(at), bold: false, italic: false });
	return out;
}

function inlines(text: string, math: string[]): Inline[] {
	const queue = [...math];
	const out: Inline[] = [];
	for (const run of emphasis(text)) {
		run.value.split(MATH).forEach((piece, i) => {
			if (i > 0)
				out.push({
					kind: 'math',
					value: queue.shift() ?? '',
					bold: run.bold,
					italic: run.italic
				});
			if (piece)
				out.push({
					kind: 'text',
					value: piece,
					bold: run.bold,
					italic: run.italic
				});
		});
	}
	return out;
}

/** Read prompt parts as paragraphs and lists. */
export function parseRichText(parts: readonly RichPart[]): Block[] {
	const blocks: Block[] = [];
	let paragraph: Line | null = null;

	const closeParagraph = () => {
		if (paragraph && paragraph.text.trim()) {
			blocks.push({
				kind: 'p',
				inlines: inlines(paragraph.text.trim(), paragraph.math)
			});
		}
		paragraph = null;
	};

	for (const line of lines(parts)) {
		const ordered = ORDERED.exec(line.text);
		const bullet = ordered ? null : BULLET.exec(line.text);
		if (ordered || bullet) {
			closeParagraph();
			const marker = (ordered ?? bullet) as RegExpExecArray;
			const item = inlines(line.text.slice(marker[0].length).trim(), line.math);
			const last = blocks[blocks.length - 1];
			if (ordered) {
				if (last?.kind === 'ol') last.items.push(item);
				else blocks.push({ kind: 'ol', start: Number(ordered[1]), items: [item] });
			} else if (last?.kind === 'ul') last.items.push(item);
			else blocks.push({ kind: 'ul', items: [item] });
		} else if (!line.text.trim()) {
			closeParagraph();
		} else if (paragraph) {
			const open: Line = paragraph;
			open.text += ' ' + line.text.trim();
			open.math.push(...line.math);
		} else {
			paragraph = { text: line.text.trim(), math: [...line.math] };
		}
	}
	closeParagraph();
	return blocks;
}
