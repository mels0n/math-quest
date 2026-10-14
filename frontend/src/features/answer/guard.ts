export const EMPTY_BOX_MESSAGE = 'Fill in the empty box first.';

/** Kid-facing reason an answer cannot be sent yet, or null when it can. */
export function submitBlocker(latex: string): string | null {
	return latex.includes(String.raw`\placeholder`) ? EMPTY_BOX_MESSAGE : null;
}

/** Notice to show after the kid edits the answer, by typing or by tapping a keypad key. */
export function noticeAfterEdit(): string {
	return '';
}
