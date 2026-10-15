<script lang="ts">
	import type { PromptPart } from '../../entities/problem';
	import { PromptView } from '../../shared/ui';

	/**
	 * Answer buttons for a multiple-choice problem. Each choice is a large button that
	 * wraps onto new rows on narrow screens; tapping one submits its index. Choices
	 * already answered wrong stay visible but are turned off.
	 */
	let {
		choices,
		wrong = [],
		disabled = false,
		onChoose
	}: {
		choices: readonly PromptPart[][];
		wrong?: readonly number[];
		disabled?: boolean;
		onChoose: (index: number) => void;
	} = $props();
</script>

<div class="choices" role="group" aria-label="Answer choices">
	{#each choices as parts, i (i)}
		{@const missed = wrong.includes(i)}
		<button
			type="button"
			class="choice"
			class:missed
			data-testid="choice"
			disabled={disabled || missed}
			onclick={() => onChoose(i)}
		>
			<PromptView {parts} />
		</button>
	{/each}
</div>

<style>
	.choices {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(min(100%, 8.5rem), 1fr));
		gap: 0.6rem;
	}
	.choice {
		min-width: 0;
		min-height: var(--mq-tap);
		padding: 0.5rem 0.75rem;
		font-family: var(--mq-sans-font);
		font-size: 1.6rem;
		font-weight: 700;
		color: var(--mq-ink);
		background: #eef0f7;
		border: 3px solid var(--mq-ink-soft);
		border-radius: var(--mq-radius);
		box-shadow: 0 3px 0 var(--mq-ink-soft);
		touch-action: manipulation;
		cursor: pointer;
		text-align: center;
	}
	.choice:active:not(:disabled) {
		transform: translateY(2px);
		box-shadow: 0 1px 0 var(--mq-ink-soft);
	}
	.choice:focus-visible {
		outline: none;
		box-shadow: var(--mq-focus);
	}
	.choice:disabled {
		cursor: default;
		opacity: 0.6;
	}
	.choice.missed {
		border-color: var(--mq-berry);
		box-shadow: 0 3px 0 var(--mq-berry);
		text-decoration: line-through;
	}
</style>
