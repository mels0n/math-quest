import { describe, expect, it } from 'vitest';
import { splitPrompt } from './split-prompt';

const text = (value: string) => ({ kind: 'text', value });
const math = (value: string) => ({ kind: 'math', value });

describe('splitPrompt', () => {
	it('splits words from the number in a place-value prompt', () => {
		expect(splitPrompt(String.raw`\text{Which digit is in the tens place of } 373\text{?}`)).toEqual([
			text('Which digit is in the tens place of '),
			math('373'),
			text('?')
		]);
	});

	it('keeps a prompt with no \\text as one math run', () => {
		expect(splitPrompt(String.raw`\frac{1}{2}+\frac{1}{3}`)).toEqual([
			math(String.raw`\frac{1}{2}+\frac{1}{3}`)
		]);
	});

	it('turns a prompt that is only \\text into one text run', () => {
		expect(splitPrompt(String.raw`\text{Count the stars.}`)).toEqual([text('Count the stars.')]);
		expect(splitPrompt(String.raw`\text{Two }\text{ parts}`)).toEqual([text('Two  parts')]);
	});

	it('handles escaped braces and other escapes inside text', () => {
		expect(splitPrompt(String.raw`\text{a \{set\} costs \$5, 50\% off}`)).toEqual([
			text('a {set} costs $5, 50% off')
		]);
	});

	it('does not treat escaped braces in math as groups', () => {
		expect(splitPrompt(String.raw`\{1,2\}\text{ is a set}`)).toEqual([
			math(String.raw`\{1,2\}`),
			text(' is a set')
		]);
	});

	it('drops grouping braces nested inside text', () => {
		expect(splitPrompt(String.raw`\text{a{b}c}`)).toEqual([text('abc')]);
	});

	it('does not match \\textbf or \\textit as \\text', () => {
		expect(splitPrompt(String.raw`\textbf{bold} x`)).toEqual([math(String.raw`\textbf{bold} x`)]);
		expect(splitPrompt(String.raw`\textit{x}`)).toEqual([math(String.raw`\textit{x}`)]);
	});

	it('leaves \\text nested inside a group in its math run whole', () => {
		const nested = String.raw`\frac{\text{apples}}{2}`;
		expect(splitPrompt(nested)).toEqual([math(nested)]);
		expect(splitPrompt(String.raw`\text{Half of } \frac{\text{6 apples}}{2}\text{?}`)).toEqual([
			text('Half of '),
			math(String.raw`\frac{\text{6 apples}}{2}`),
			text('?')
		]);
	});

	it('makes the rest of the prompt text when \\text is never closed', () => {
		expect(splitPrompt(String.raw`3+\text{oops`)).toEqual([math('3+'), text('oops')]);
	});

	it('keeps an unclosed math group as math', () => {
		expect(splitPrompt(String.raw`\frac{1}{2`)).toEqual([math(String.raw`\frac{1}{2`)]);
	});

	it('treats \\text without a brace group as math', () => {
		expect(splitPrompt(String.raw`\text x`)).toEqual([math(String.raw`\text x`)]);
	});

	it('returns nothing for an empty or blank prompt', () => {
		expect(splitPrompt('')).toEqual([]);
		expect(splitPrompt('   ')).toEqual([]);
	});

	it('allows spaces between \\text and its group', () => {
		expect(splitPrompt(String.raw`\text {hi} 4`)).toEqual([text('hi'), math('4')]);
	});
});
