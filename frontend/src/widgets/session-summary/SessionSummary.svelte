<script lang="ts">
	import type { Summary } from '../../entities/problem';
	import { PixelButton } from '../../shared/ui';
	import { SUMMARY_COPY, accuracyText, durationText, summaryTitle } from './summary';

	let {
		summary,
		busy = false,
		onPlayAgain,
		onPractice
	}: {
		summary: Summary;
		busy?: boolean;
		onPlayAgain: () => void;
		onPractice: () => void;
	} = $props();

	const accuracy = $derived(accuracyText(summary));
</script>

<section class="summary" data-testid="summary" aria-labelledby="summary-title">
	<h2 id="summary-title" class="mq-pixel">{summaryTitle(summary)}</h2>
	{#if summary.problems_scored === 0}
		<p class="lead">{SUMMARY_COPY.none}</p>
	{:else}
		<dl class="stats">
			<div>
				<dt>{SUMMARY_COPY.solved}</dt>
				<dd data-testid="summary-solved">{summary.problems_solved}</dd>
			</div>
			{#if accuracy}
				<div>
					<dt>{SUMMARY_COPY.accuracy}</dt>
					<dd data-testid="summary-accuracy">{accuracy}</dd>
				</div>
			{/if}
			<div>
				<dt>{SUMMARY_COPY.time}</dt>
				<dd>{durationText(summary.seconds)}</dd>
			</div>
		</dl>
	{/if}
	{#if summary.newly_mastered.length > 0}
		<div class="group mastered">
			<h3 class="mq-pixel">{SUMMARY_COPY.mastered}</h3>
			<ul>
				{#each summary.newly_mastered as skill (skill.skill_id)}
					<li><span aria-hidden="true">&#9733;</span> {skill.name}</li>
				{/each}
			</ul>
		</div>
	{/if}
	{#if summary.skills_practiced.length > 0}
		<div class="group">
			<h3 class="mq-pixel">{SUMMARY_COPY.practiced}</h3>
			<ul data-testid="summary-skills">
				{#each summary.skills_practiced as skill (skill.skill_id)}
					<li>{skill.name}</li>
				{/each}
			</ul>
		</div>
	{/if}
	<div class="actions">
		<PixelButton variant="mint" disabled={busy} onclick={onPlayAgain}>{SUMMARY_COPY.playAgain}</PixelButton>
		<PixelButton variant="gold" disabled={busy} onclick={onPractice}>{SUMMARY_COPY.practice}</PixelButton>
	</div>
</section>

<style>
	.summary {
		display: flex;
		flex-direction: column;
		gap: 1rem;
		padding: 1.25rem;
		background: var(--mq-navy);
		border: 4px solid var(--mq-gold);
		box-shadow: 0 4px 0 #000;
	}
	h2 {
		margin: 0;
		font-size: 1rem;
		line-height: 1.6;
		color: var(--mq-gold);
		text-align: center;
	}
	h3 {
		margin: 0 0 0.5rem;
		font-size: 0.7rem;
		line-height: 1.6;
		color: var(--mq-mint);
	}
	.lead {
		margin: 0;
		font-size: 1.2rem;
		text-align: center;
	}
	.stats {
		display: grid;
		gap: 0.5rem;
		margin: 0;
		padding: 1rem;
		background: var(--mq-card);
		color: var(--mq-ink);
		border-radius: var(--mq-radius);
	}
	.stats div {
		display: flex;
		flex-wrap: wrap;
		justify-content: space-between;
		gap: 0.25rem 1rem;
	}
	dt {
		font-size: 1.05rem;
		color: var(--mq-ink-soft);
	}
	dd {
		margin: 0;
		font-size: 1.15rem;
		font-weight: 700;
	}
	ul {
		margin: 0;
		padding-left: 1.25rem;
		font-size: 1.15rem;
		line-height: 1.5;
	}
	.mastered ul {
		list-style: none;
		padding-left: 0;
		color: var(--mq-gold);
		font-weight: 700;
	}
	.actions {
		display: flex;
		flex-wrap: wrap;
		justify-content: center;
		gap: 0.75rem;
	}
</style>
