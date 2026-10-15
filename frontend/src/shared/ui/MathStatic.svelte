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
		overflow-x: auto;
		/* A scrolling inline-block sits on its bottom edge; centre it on the text instead. */
		vertical-align: middle;
	}
</style>
