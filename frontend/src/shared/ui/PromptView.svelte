<script lang="ts">
	import 'mathlive/static.css';
	import { convertLatexToMarkup } from 'mathlive';
	import { watchFit } from './fit-to-width';
	import { splitPrompt } from './split-prompt';

	/** A problem prompt: words wrap as plain text, math is set inline and shrinks to fit. */
	let { latex }: { latex: string } = $props();

	const runs = $derived(
		splitPrompt(latex).map((run) =>
			run.kind === 'math'
				? { ...run, markup: convertLatexToMarkup(run.value, { defaultMode: 'math' }) }
				: { ...run, markup: '' }
		)
	);

	let container: HTMLElement | undefined = $state();

	// Effects run after the DOM update, so a new prompt is measured with its new markup.
	$effect(() => {
		void runs;
		if (!container) return;
		return watchFit(container);
	});
</script>

<div class="runs" bind:this={container}>
	{#each runs as run, i (i)}
		{#if run.kind === 'text'}
			<span class="run text">{run.value}</span>
		{:else}
			<span class="run math" role="img" aria-label={run.value}>{@html run.markup}</span>
		{/if}
	{/each}
</div>

<style>
	.runs {
		width: 100%;
		padding: 0;
		overflow-wrap: anywhere;
	}
	.text {
		white-space: normal;
	}
	.math {
		display: inline-block;
		white-space: nowrap;
		vertical-align: middle;
	}
</style>
