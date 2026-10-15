import type { Summary } from '../../entities/problem';

export const SUMMARY_COPY = {
	adventureTitle: 'QUEST COMPLETE!',
	practiceTitle: 'PRACTICE DONE!',
	accuracy: 'Right answers',
	time: 'Time',
	practiced: 'Skills you worked on',
	mastered: 'New skills mastered!',
	none: 'No problems this time. Ready when you are!',
	playAgain: 'Play again',
	practice: 'Practice'
} as const;

function plural(n: number, word: string): string {
	return `${n} ${word}${n === 1 ? '' : 's'}`;
}

/** "45 seconds", "1 minute", "4 minutes 5 seconds". */
export function durationText(seconds: number): string {
	const total = Math.max(0, Math.round(seconds));
	if (total < 60) return plural(total, 'second');
	const minutes = Math.floor(total / 60);
	const rest = total % 60;
	return rest === 0 ? plural(minutes, 'minute') : `${plural(minutes, 'minute')} ${plural(rest, 'second')}`;
}

/** "9 of 11 (82%)", or null when nothing was scored. */
export function accuracyText(summary: Summary): string | null {
	if (summary.accuracy === null || summary.problems_scored === 0) return null;
	const percent = Math.round(summary.accuracy * 100);
	return `${summary.problems_solved} of ${summary.problems_scored} (${percent}%)`;
}

export function summaryTitle(summary: Summary): string {
	return summary.mode === 'practice' ? SUMMARY_COPY.practiceTitle : SUMMARY_COPY.adventureTitle;
}
