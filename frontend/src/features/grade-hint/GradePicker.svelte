<script lang="ts">
	import { GRADE_HINTS } from '../../entities/problem';
	import type { GradeHint } from '../../entities/problem';
	import { PixelButton } from '../../shared/ui';
	import { GRADE_COPY, gradeLabel } from './grade';

	let {
		onPick,
		disabled = false
	}: { onPick: (grade: GradeHint | null) => void; disabled?: boolean } = $props();
</script>

<section class="grade" aria-labelledby="grade-question">
	<h2 id="grade-question" class="mq-pixel">{GRADE_COPY.question}</h2>
	<p>{GRADE_COPY.why}</p>
	<div class="grid" role="group" aria-label={GRADE_COPY.question}>
		{#each GRADE_HINTS as grade (grade)}
			<PixelButton variant="gold" label={gradeLabel(grade)} {disabled} onclick={() => onPick(grade)}>
				{grade}
			</PixelButton>
		{/each}
	</div>
	<PixelButton variant="plain" {disabled} onclick={() => onPick(null)}>{GRADE_COPY.skip}</PixelButton>
</section>

<style>
	.grade {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 1rem;
		padding: 1.25rem;
		background: var(--mq-navy);
		border: 4px solid var(--mq-mint);
		text-align: center;
	}
	h2 {
		margin: 0;
		font-size: 0.95rem;
		line-height: 1.6;
		color: var(--mq-gold);
	}
	p {
		margin: 0;
		font-size: 1.15rem;
	}
	.grid {
		display: grid;
		grid-template-columns: repeat(3, minmax(0, 4.5rem));
		gap: 0.75rem;
		justify-content: center;
	}
</style>
