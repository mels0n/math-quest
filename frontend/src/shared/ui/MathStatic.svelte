<script lang="ts">
	import 'mathlive/static.css';
	import { convertLatexToMarkup } from 'mathlive';

	let {
		latex,
		label,
		class: extraClass = ''
	}: { latex: string; label?: string; class?: string } = $props();

	const markup = $derived(convertLatexToMarkup(latex, { defaultMode: 'math' }));
</script>

<span class="math {extraClass}" role="img" aria-label={label ?? latex}>{@html markup}</span>

<style>
	.math {
		display: inline-block;
		max-width: 100%;
		/* Prompts are shrunk to fit their width (fit-to-width), so this only guards the
		   extreme case. It must be clip, not auto: auto turns the vertical axis into a
		   scroller too, and a stacked fraction is taller than the line box, so every
		   fraction prompt grew its own scrollbar and lost the tops of its numerators. */
		overflow-x: clip;
		vertical-align: middle;
	}
</style>
