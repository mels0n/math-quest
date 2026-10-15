/**
 * Splits a LaTeX prompt into plain-text runs and math runs.
 *
 * Interim: prompts arrive as one LaTeX string whose words sit in top-level
 * `\text{...}` groups. Once the generators send prompts as structured parts, this
 * splitter goes away.
 *
 * Rules:
 * - Only a top-level `\text{...}` (not inside any brace group) becomes a text run.
 *   A `\text` inside a group, such as `\frac{\text{a}}{2}`, stays in its math run
 *   whole, so the math is never cut in the middle of a group.
 * - `\textbf`, `\textit` and other longer command names are math, not `\text`.
 * - Inside a text run, grouping braces are dropped, `\{ \} \% \$ \& \# \_` become
 *   the character and `\ ` or `~` a space. Other commands are kept as written.
 * - A `\text{` that is never closed makes the rest of the prompt a text run.
 * - Math runs are trimmed and empty ones dropped; neighbouring text runs merge.
 */

export interface PromptRun {
	kind: 'text' | 'math';
	value: string;
}

const LETTER = /[A-Za-z]/;
const TEXT_ESCAPES = new Set(['{', '}', '%', '$', '&', '#', '_']);

/** Length of the control sequence starting at `i` (which must be a backslash). */
function commandLength(src: string, i: number): number {
	if (i + 1 >= src.length) return 1;
	if (!LETTER.test(src[i + 1] as string)) return 2;
	let j = i + 1;
	while (j < src.length && LETTER.test(src[j] as string)) j += 1;
	return j - i;
}

/** Reads a brace group whose `{` is at `open`; returns its text and the index after `}`. */
function readTextGroup(src: string, open: number): { text: string; end: number } {
	let depth = 1;
	let text = '';
	let i = open + 1;
	while (i < src.length) {
		const ch = src[i] as string;
		if (ch === '\\') {
			const len = commandLength(src, i);
			const next = src[i + 1];
			if (len === 2 && next !== undefined && TEXT_ESCAPES.has(next)) text += next;
			else if (len === 2 && next === ' ') text += ' ';
			else text += src.slice(i, i + len);
			i += len;
			continue;
		}
		if (ch === '{') depth += 1;
		else if (ch === '}') {
			depth -= 1;
			if (depth === 0) return { text, end: i + 1 };
		} else if (ch === '~') text += ' ';
		else text += ch;
		i += 1;
	}
	return { text, end: src.length };
}

/** Index of the `{` that opens a `\text` argument at `i`, or -1 when there is none. */
function textGroupStart(src: string, i: number): number {
	let j = i + '\\text'.length;
	while (j < src.length && /\s/.test(src[j] as string)) j += 1;
	return src[j] === '{' ? j : -1;
}

export function splitPrompt(latex: string): PromptRun[] {
	const runs: PromptRun[] = [];
	const push = (kind: PromptRun['kind'], raw: string) => {
		const value = kind === 'math' ? raw.trim() : raw;
		if (value === '') return;
		const last = runs[runs.length - 1];
		if (kind === 'text' && last?.kind === 'text') last.value += value;
		else runs.push({ kind, value });
	};

	let depth = 0;
	let mathStart = 0;
	let i = 0;
	while (i < latex.length) {
		const ch = latex[i] as string;
		if (ch === '\\') {
			const len = commandLength(latex, i);
			const open =
				depth === 0 && latex.slice(i + 1, i + len) === 'text' ? textGroupStart(latex, i) : -1;
			if (open === -1) {
				i += len;
				continue;
			}
			push('math', latex.slice(mathStart, i));
			const { text, end } = readTextGroup(latex, open);
			push('text', text);
			i = end;
			mathStart = end;
			continue;
		}
		if (ch === '{') depth += 1;
		else if (ch === '}' && depth > 0) depth -= 1;
		i += 1;
	}
	push('math', latex.slice(mathStart));
	return runs;
}
