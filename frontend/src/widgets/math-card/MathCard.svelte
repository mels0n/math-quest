<script lang="ts">
	import { tick } from 'svelte';
	import { AnswerField, ChoiceField } from '../../features/answer';
	import { MAX_ATTEMPTS, PLAY_COPY, keypadProfile } from '../../entities/problem';
	import type {
		Answer,
		Explanation,
		Feedback,
		Mastery,
		Problem,
		PromptPart
	} from '../../entities/problem';
	import { MathStatic, PixelButton, PromptView, ProgressBar, RichText } from '../../shared/ui';
	import { VisualView } from '../../shared/visuals';
	import type { CardFeedback } from './card-feedback';
	import { helpButtons } from './help';

	let {
		problem,
		attemptsLeft,
		feedback,
		mastery,
		revealedLatex,
		revealedChoice = null,
		finished,
		busy,
		onSubmit,
		onNext,
		mistakeFeedback = null,
		hints = [],
		explanation = null,
		missed = false,
		onHint,
		onExplain,
		hearts = true
	}: {
		problem: Problem;
		attemptsLeft: number;
		feedback: CardFeedback | null;
		mastery: Mastery | null;
		revealedLatex: string | null;
		revealedChoice?: number | null;
		finished: boolean;
		busy: boolean;
		onSubmit: (answer: Answer) => void;
		onNext: () => void;
		/** Feedback on the last wrong answer, shown right under the verdict line. */
		mistakeFeedback?: Feedback | null;
		/** Hint levels shown so far on this problem, first level first. */
		hints?: PromptPart[][];
		/** The latest "explain it another way". */
		explanation?: Explanation | null;
		/** The problem has had a wrong answer. */
		missed?: boolean;
		/** Without these the card shows no help buttons (a lesson's try-it). */
		onHint?: () => void;
		onExplain?: () => void;
		/** Show the tries left (placement has none). */
		hearts?: boolean;
	} = $props();

	const buttons = $derived(helpButtons(problem, { hintsShown: hints.length, missed, finished }));

	let answer: ReturnType<typeof AnswerField> | undefined = $state();

	/**
	 * The one live region: it reads out the verdict with its feedback, each new hint and
	 * each new explanation. The notes on screen are not live regions themselves.
	 */
	let announcement = $state('');
	let hintBox: HTMLElement | undefined = $state();
	let explainBox: HTMLElement | undefined = $state();
	let hintsSeen = 0;
	const spoken = (parts: readonly PromptPart[]) => parts.map((p) => p.value).join('');

	$effect(() => {
		const said = [feedback?.text ?? '', mistakeFeedback ? spoken(mistakeFeedback.text) : ''];
		announcement = said.filter(Boolean).join(' ');
	});

	$effect(() => {
		const count = hints.length;
		const last = hints[count - 1];
		if (count > hintsSeen && last) {
			announcement = `${PLAY_COPY.hint} ${count}. ${spoken(last)}`;
			void tick().then(() =>
				hintBox?.querySelector<HTMLElement>('[data-testid="hint"]:last-child')?.focus()
			);
		}
		hintsSeen = count;
	});

	$effect(() => {
		if (!explanation) return;
		announcement = `${PLAY_COPY.explanation}. ${spoken(explanation.body)}`;
		void tick().then(() => explainBox?.focus());
	});
	/** Word problems read as sentences, so they use a calmer reading size. */
	const WORDY_TEXT = 40;
	const wordy = $derived(
		problem.prompt.reduce((n, part) => n + (part.kind === 'text' ? part.value.length : 0), 0) >
			WORDY_TEXT
	);
	/** Choices of this problem answered wrong so far, and the one awaiting a verdict. */
	let wrongChoices = $state<number[]>([]);
	let pendingChoice: number | null = null;

	$effect(() => {
		void problem.problem_id;
		wrongChoices = [];
		pendingChoice = null;
	});

	function choose(index: number) {
		pendingChoice = index;
		onSubmit({ choice: index });
	}

	/** After a miss: empties typed input, or turns off the choice just tried. */
	export function resetInput() {
		answer?.clear();
		if (pendingChoice !== null && !wrongChoices.includes(pendingChoice)) {
			wrongChoices = [...wrongChoices, pendingChoice];
		}
		pendingChoice = null;
	}
</script>

<section class="card" aria-label="Math problem">
	<div class="top">
		<h2 class="skill">{problem.skill_name}</h2>
		{#if hearts}
			<span class="hearts" role="img" aria-label="{attemptsLeft} tries left">
				{#each Array.from({ length: MAX_ATTEMPTS }, (_, i) => i) as i (i)}
					<span class:lost={i >= attemptsLeft}>&#9829;</span>
				{/each}
			</span>
		{/if}
	</div>

	<div class="prompt" class:wordy data-testid="prompt">
		<PromptView parts={problem.prompt} />
	</div>

	{#if mastery}
		<div class="mastery">
			<ProgressBar value={mastery.progress} label="{problem.skill_name} progress" />
		</div>
	{/if}

	{#if mastery?.state === 'mastered'}
		<p class="cheer" role="status" data-testid="mastered">&#9733; Skill mastered! &#9733;</p>
	{/if}

	<p class="feedback {feedback?.tone ?? ''}" class:empty={!feedback && mistakeFeedback} data-testid="feedback">
		{feedback?.text ?? ''}
	</p>

	{#if mistakeFeedback}
		<div class="note {mistakeFeedback.kind}" data-testid="mistake-feedback">
			<RichText parts={mistakeFeedback.text} />
		</div>
	{/if}

	{#if revealedLatex !== null}
		<p class="reveal">
			The answer is <MathStatic latex={revealedLatex} />
		</p>
	{:else if revealedChoice !== null && problem.choices?.[revealedChoice]}
		<div class="reveal choice-reveal" data-testid="revealed-choice">
			<span>The answer is</span>
			<PromptView parts={problem.choices[revealedChoice]} />
		</div>
	{/if}

	{#if finished}
		<div class="next">
			<PixelButton variant="mint" onclick={onNext}>Next</PixelButton>
		</div>
	{:else if problem.choices && problem.choices.length > 0}
		<ChoiceField
			choices={problem.choices}
			wrong={wrongChoices}
			disabled={busy}
			onChoose={choose}
		/>
	{:else}
		{#key problem.problem_id}
			<AnswerField
				bind:this={answer}
				profile={keypadProfile(problem.keypad)}
				disabled={busy}
				onSubmit={(latex) => onSubmit({ latex })}
			/>
		{/key}
	{/if}

	{#if (onHint && buttons.hint) || (onExplain && buttons.explain)}
		<div class="help">
			{#if onHint && buttons.hint}
				<PixelButton variant="plain" onclick={onHint}>{buttons.hintLabel}</PixelButton>
			{/if}
			{#if onExplain && buttons.explain}
				<PixelButton variant="plain" label={PLAY_COPY.explain} onclick={onExplain}
					>{PLAY_COPY.anotherWay}</PixelButton
				>
			{/if}
		</div>
	{/if}

	{#if hints.length > 0}
		<div class="hints" bind:this={hintBox}>
			{#each hints as hint, i (i)}
				<div class="note hint" data-testid="hint" tabindex="-1">
					<span class="label">{PLAY_COPY.hint} {i + 1}</span>
					<RichText parts={hint} />
				</div>
			{/each}
		</div>
	{/if}

	{#if explanation}
		<div class="note explain" data-testid="explanation" tabindex="-1" bind:this={explainBox}>
			<span class="label">{PLAY_COPY.explanation}</span>
			<RichText parts={explanation.body} />
			{#if explanation.visual}
				<div class="visual"><VisualView visual={explanation.visual} /></div>
			{/if}
		</div>
	{/if}

	<div class="sr-only" role="status" aria-live="polite" data-testid="announcer">{announcement}</div>
</section>

<style>
	.card {
		position: relative;
		display: flex;
		flex-direction: column;
		gap: 0.9rem;
		padding: 1.25rem;
		color: var(--mq-ink);
		background: var(--mq-card);
		border: 4px solid var(--mq-gold);
		border-radius: var(--mq-radius);
		font-family: var(--mq-sans-font);
	}
	.top {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 0.75rem;
	}
	.skill {
		margin: 0;
		font-family: var(--mq-sans-font);
		font-size: 1.1rem;
		font-weight: 700;
		color: var(--mq-ink-soft);
		letter-spacing: 0;
	}
	.hearts {
		font-size: 1.6rem;
		color: var(--mq-berry);
		letter-spacing: 0.15em;
	}
	.hearts .lost {
		color: var(--mq-line);
	}
	.prompt {
		font-size: 2.6rem;
		text-align: center;
		padding: 0.75rem 0;
		min-height: 5rem;
		min-width: 0;
	}
	.prompt.wordy {
		font-size: 1.75rem;
		line-height: 1.35;
	}
	.mastery {
		padding: 0 0.25rem;
	}
	.cheer {
		margin: 0;
		padding: 0.6rem;
		text-align: center;
		font-family: var(--mq-pixel-font);
		font-size: 0.8rem;
		color: var(--mq-navy-deep);
		background: var(--mq-gold);
		animation: pop 0.5s ease-out;
	}
	.feedback {
		margin: 0;
		min-height: 2rem;
		font-size: 1.35rem;
		font-weight: 700;
	}
	.feedback.empty {
		display: none;
	}
	.feedback.good {
		color: #04704f;
	}
	.feedback.try {
		color: #b0243f;
	}
	.feedback.info {
		color: var(--mq-ink-soft);
	}
	.reveal {
		margin: 0;
		font-size: 1.4rem;
	}
	.choice-reveal {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: 0.4rem;
	}
	.choice-reveal :global(.runs) {
		width: auto;
		min-width: 0;
	}
	.next {
		display: flex;
		justify-content: center;
	}
	.note {
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
		padding: 0.75rem 0.9rem;
		font-size: 1.15rem;
		line-height: 1.4;
		background: #fff8e1;
		border-left: 6px solid var(--mq-gold);
		border-radius: var(--mq-radius);
		min-width: 0;
	}
	.note.misconception {
		background: #fdecef;
		border-left-color: var(--mq-berry);
	}
	.note.explain {
		background: #e6faf4;
		border-left-color: var(--mq-mint);
	}
	.note :global(p:last-child),
	.note :global(ol:last-child),
	.note :global(ul:last-child) {
		margin-bottom: 0;
	}
	.note:focus {
		outline: none;
	}
	.note:focus-visible {
		outline: 3px solid var(--mq-navy);
	}
	.hints {
		display: flex;
		flex-direction: column;
		gap: 0.9rem;
	}
	.sr-only {
		position: absolute;
		width: 1px;
		height: 1px;
		padding: 0;
		margin: -1px;
		overflow: hidden;
		clip: rect(0, 0, 0, 0);
		white-space: nowrap;
		border: 0;
	}
	.label {
		font-size: 0.9rem;
		font-weight: 700;
		color: var(--mq-ink-soft);
	}
	.visual {
		max-width: 100%;
		overflow: hidden;
	}
	.help {
		display: flex;
		flex-wrap: wrap;
		justify-content: center;
		gap: 0.75rem;
	}
	@keyframes pop {
		from {
			transform: scale(0.8);
		}
		to {
			transform: scale(1);
		}
	}
</style>
