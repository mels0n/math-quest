<script module lang="ts">
	/** One part of a prompt: words, or a math expression in LaTeX. */
	export interface PromptRun {
		kind: 'text' | 'math';
		value: string;
	}
</script>

<script lang="ts">
	import MathStatic from './MathStatic.svelte';
	import { MATH_RUN_CLASS, watchFit } from './fit-to-width';

	/** A problem prompt: words wrap as plain text, math is set inline and shrinks to fit. */
	let { parts }: { parts: readonly PromptRun[] } = $props();

	let container: HTMLElement | undefined = $state();

	// Effects run after the DOM update, so a new prompt is measured with its new markup.
	$effect(() => {
		void parts;
		if (!container) return;
		return watchFit(container);
	});
</script>

<div class="runs" bind:this={container}>
	{#each parts as part, i (i)}
		{#if part.kind === 'text'}
			<span class="run text">{part.value}</span>
		{:else}
			<MathStatic latex={part.value} class="run {MATH_RUN_CLASS}" />
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
</style>
