import { ApiError, commonErrorMessage } from '../../shared/api';

export interface Done {
	ok: boolean;
}

export interface AdminPlayer {
	id: string;
	nickname: string;
	hidden: boolean;
	created_at: string;
	last_seen: string | null;
}

export interface PinReset {
	recovery_word: string;
}

export interface SignupWordState {
	set: boolean;
}

export interface ListParams {
	query?: string;
	offset?: number;
	limit?: number;
}

/** Delete stays disabled until the typed text equals the nickname exactly. */
export const canDelete = (nickname: string, typed: string): boolean =>
	nickname.length > 0 && typed === nickname;

export const isValidPin = (pin: string): boolean => /^[0-9]{4}$/.test(pin);

/** Mirrors the backend nickname rule: 3 to 16 of letters, numbers, space, underscore, hyphen. */
export const isValidNickname = (nickname: string): boolean =>
	/^[A-Za-z0-9 _-]{3,16}$/.test(nickname);

export const isValidSignupWord = (word: string): boolean => /^[A-Za-z]{3,32}$/.test(word);

export const NOT_ON_LAN = 'Admin is only available on the home network.';

const CODE_COPY: Record<string, string> = {
	unauthorized: 'That password is not right, or your session ended. Sign in again.',
	nickname_taken: 'Another player already has that nickname.',
	nickname: 'Use 3 to 16 letters, numbers, spaces, - or _.',
	signup_word: 'Use 3 to 32 letters only.',
	nickname_blocked: 'That nickname is not allowed. Try another.',
	not_found: 'That player no longer exists. Refresh the list.',
	invalid_request: 'Please check what you entered and try again.',
	csrf: 'The page is out of date. Reload it and try again.',
	busy: 'That player is busy right now. Try again in a moment.'
};

/** Plain-language text for a failed admin request; never shows the raw error code. */
export function adminErrorMessage(err: unknown): string {
	if (err instanceof ApiError) {
		if (err.status === 429 && err.code === 'locked') return CODE_COPY.busy as string;
		if (err.status !== 429 && Object.hasOwn(CODE_COPY, err.code)) {
			return CODE_COPY[err.code] as string;
		}
	}
	return commonErrorMessage(err, 'Too many tries.');
}

export type NotFoundVerdict = 'offlan' | 'login' | 'missing' | 'unknown';

/**
 * The backend answers 404 both for an off-LAN client and for an unknown player. After a 404 from
 * a player action, the result of a follow-up session check (null when it succeeded) tells which.
 */
export function resolveNotFound(sessionCheckFailure: unknown): NotFoundVerdict {
	if (sessionCheckFailure === null) return 'missing';
	if (sessionCheckFailure instanceof ApiError) {
		if (sessionCheckFailure.status === 404) return 'offlan';
		if (sessionCheckFailure.status === 401) return 'login';
	}
	return 'unknown';
}

/** One part of rendered content: words (which may hold simple Markdown) or LaTeX math. */
export interface ContentPart {
	kind: 'text' | 'math';
	value: string;
}

export interface CoverageGap {
	field: string;
	have: number;
	want: number;
}

export interface SkillCoverage {
	skill_id: string;
	name: string;
	tiers: number;
	misconceptions: number;
	/** null when word problems do not fit the skill. */
	word_templates: number | null;
	/** null when the skill is not banked. */
	bank_items: number | null;
	lesson: boolean;
	hints: number;
	explanations: number;
	gaps: CoverageGap[];
}

export interface RegionCoverage {
	region_id: string;
	name: string;
	complete: boolean;
	skills: SkillCoverage[];
}

export interface ContentPack {
	id: string;
	title: string;
	version: string;
	live: boolean;
	complete_regions: string[];
	regions: RegionCoverage[];
}

export interface ContentOverview {
	packs: ContentPack[];
}

export interface ContentVisual {
	kind: string;
	params: Record<string, unknown>;
}

export interface MisconceptionPreview {
	key: string;
	answer_latex: string;
	feedback: ContentPart[] | null;
}

export interface ProblemPreview {
	seed: number;
	tier: number;
	prompt: ContentPart[];
	answer_latex: string | null;
	choices: ContentPart[][] | null;
	correct_choice: number | null;
	misconceptions: MisconceptionPreview[];
	error: string | null;
}

export interface LessonPreview {
	screens: {
		title: string;
		body: ContentPart[];
		visual: ContentVisual | null;
	}[];
	worked_prompt: ContentPart[];
	worked_steps: ContentPart[][];
	try_it_tier: number;
	try_it_seed: number | null;
}

export interface SkillPreview {
	skill_id: string;
	name: string;
	region: string;
	grade_band: string;
	keypad: string;
	tier_labels: string[];
	tier: number;
	seeds: number[];
	coverage: SkillCoverage;
	problems: ProblemPreview[];
	lesson: LessonPreview | null;
	hints: ContentPart[][] | null;
	explanations: { style: string; body: ContentPart[]; visual: ContentVisual | null }[] | null;
	word_templates: {
		id: string;
		grade_band: string;
		answer_from: 'generator_answer' | 'expression';
		samples: ProblemPreview[];
	}[];
	bank_items: { id: string; kind: 'choice' | 'expr'; sample: ProblemPreview }[];
	errors: string[];
}

export interface PreviewParams {
	seed?: number;
	tier?: number;
}

/** Largest seed the preview accepts. */
export const MAX_PREVIEW_SEED = 2 ** 31 - 1;

/** A seed typed by the admin: a whole number in range, or undefined for the sample seeds. */
export function parseSeed(raw: string): number | undefined | null {
	const trimmed = raw.trim();
	if (trimmed === '') return undefined;
	if (!/^[0-9]{1,10}$/.test(trimmed)) return null;
	const seed = Number(trimmed);
	return seed <= MAX_PREVIEW_SEED ? seed : null;
}

/** "have/want" for a coverage target, or "n/a" when the target does not apply. */
export function coverageCell(have: number | null, want: number): string {
	if (have === null) return 'n/a';
	return `${have}/${want}`;
}
