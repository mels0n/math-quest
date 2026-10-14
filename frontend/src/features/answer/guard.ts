export const EMPTY_BOX_MESSAGE = 'Fill in the empty box first.';

/** Kid-facing reason an answer cannot be sent yet, or null when it can. */
export function submitBlocker(latex: string): string | null {
	return latex.includes(String.raw`\placeholder`) ? EMPTY_BOX_MESSAGE : null;
}

/** Notice to show after the kid edits the answer (typing or a keypad tap): the empty-box notice goes away. */
export function noticeAfterEdit(current: string): string {
	return current === EMPTY_BOX_MESSAGE ? '' : current;
}
