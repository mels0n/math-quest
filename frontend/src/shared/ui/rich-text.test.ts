import { describe, expect, it } from 'vitest';
import { parseRichText, type Inline } from './rich-text';

const text = (value: string) => ({ kind: 'text' as const, value });
const math = (value: string) => ({ kind: 'math' as const, value });
const plain = (value: string): Inline => ({
	kind: 'text',
	value,
	bold: false,
	italic: false
});

describe('parseRichText', () => {
	it('keeps HTML as literal text and never produces markup', () => {
		const blocks = parseRichText([text('<script>alert(1)</script> & <b>hi</b>')]);
		expect(blocks).toEqual([
			{ kind: 'p', inlines: [plain('<script>alert(1)</script> & <b>hi</b>')] }
		]);
	});

	it('does not read HTML hidden in list items or emphasis', () => {
		const blocks = parseRichText([text('- <img src=x onerror=alert(1)>\n**<i>x</i>**')]);
		expect(blocks).toEqual([
			{ kind: 'ul', items: [[plain('<img src=x onerror=alert(1)>')]] },
			{
				kind: 'p',
				inlines: [{ kind: 'text', value: '<i>x</i>', bold: true, italic: false }]
			}
		]);
	});

	it('splits paragraphs on blank lines and joins wrapped lines', () => {
		const blocks = parseRichText([text('One line\nstill one.\n\nTwo.')]);
		expect(blocks).toEqual([
			{ kind: 'p', inlines: [plain('One line still one.')] },
			{ kind: 'p', inlines: [plain('Two.')] }
		]);
	});

	it('reads numbered and bulleted lists', () => {
		const blocks = parseRichText([text('3. Third\n4. Fourth\n- dot\n* star')]);
		expect(blocks).toEqual([
			{ kind: 'ol', start: 3, items: [[plain('Third')], [plain('Fourth')]] },
			{ kind: 'ul', items: [[plain('dot')], [plain('star')]] }
		]);
	});

	it('reads bold and italic, and leaves a lone star alone', () => {
		const [block] = parseRichText([text('A **big** and *small* and _tiny_ 2 * 3 add_on')]);
		expect(block).toEqual({
			kind: 'p',
			inlines: [
				plain('A '),
				{ kind: 'text', value: 'big', bold: true, italic: false },
				plain(' and '),
				{ kind: 'text', value: 'small', bold: false, italic: true },
				plain(' and '),
				{ kind: 'text', value: 'tiny', bold: false, italic: true },
				plain(' 2 * 3 add_on')
			]
		});
	});

	it('keeps math parts in place, inside lists and emphasis too', () => {
		const blocks = parseRichText([
			text('Look at '),
			math('8 + 5'),
			text('.\n1. Start at **'),
			math('8'),
			text('**.')
		]);
		expect(blocks).toEqual([
			{
				kind: 'p',
				inlines: [
					plain('Look at '),
					{ kind: 'math', value: '8 + 5', bold: false, italic: false },
					plain('.')
				]
			},
			{
				kind: 'ol',
				start: 1,
				items: [
					[plain('Start at '), { kind: 'math', value: '8', bold: true, italic: false }, plain('.')]
				]
			}
		]);
	});

	it('returns nothing for empty input', () => {
		expect(parseRichText([])).toEqual([]);
		expect(parseRichText([text('\n\n')])).toEqual([]);
	});
});
