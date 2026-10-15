<script lang="ts">
	import { AnswerField } from '../../features/answer';
	import { MAX_ATTEMPTS, keypadProfile } from '../../entities/problem';
	import type { Mastery, Problem } from '../../entities/problem';
	import { MathStatic, PixelButton, PromptView, ProgressBar } from '../../shared/ui';
	import type { CardFeedback } from './card-feedback';

	let {
		problem,
		attemptsLeft,
		feedback,
		mastery,
		revealedLatex,
		finished,
		busy,
		onSubmit,
		onNext
	}: {
		problem: Problem;
		attemptsLeft: number;
		feedback: CardFeedback | null;
		mastery: Mastery | null;
		revealedLatex: string | null;
		finished: boolean;
		busy: boolean;
		onSubmit: (latex: string) => void;
		onNext: () => void;
	} = $props();

	let answer: ReturnType<typeof AnswerField> | undefined = $state();

	/** Empties the input after a miss so the next try starts clean. */
	export function resetInput() {
		answer?.clear();
	}
</script>

<section class="card" aria-label="Math problem">
	<div class="top">
		<h2 class="skill">{problem.skill_name}</h2>
		<span class="hearts" role="img" aria-label="{attemptsLeft} tries left">
			{#each Array.from({ length: MAX_ATTEMPTS }, (_, i) => i) as i (i)}
				<span class:lost={i >= attemptsLeft}>&#9829;</span>
			{/each}
		</span>
	</div>

	<div class="prompt" data-testid="prompt">
		<PromptView latex={problem.prompt_latex} />
	</div>

	{#if mastery}
		<div class="mastery">
			<ProgressBar value={mastery.progress} label="{problem.skill_name} progress" />
		</div>
	{/if}

	{#if mastery?.state === 'mastered'}
		<p class="cheer" role="status" data-testid="mastered">&#9733; Skill mastered! &#9733;</p>
	{/if}

	<p class="feedback {feedback?.tone ?? ''}" role="status" aria-live="polite" data-testid="feedback">
		{feedback?.text ?? ''}
	</p>

	{#if revealedLatex !== null}
		<p class="reveal">
			The answer is <MathStatic latex={revealedLatex} />
		</p>
	{/if}

	{#if finished}
		<div class="next">
			<PixelButton variant="mint" onclick={onNext}>Next</PixelButton>
		</div>
	{:else}
		{#key problem.problem_id}
			<AnswerField
				bind:this={answer}
				profile={keypadProfile(problem.keypad)}
				disabled={busy}
				{onSubmit}
			/>
		{/key}
	{/if}
</section>

<style>
	.card {
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
	.next {
		display: flex;
		justify-content: center;
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
