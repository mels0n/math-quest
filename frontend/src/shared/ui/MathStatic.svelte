<script lang="ts">
	import 'mathlive/static.css';
	import { convertLatexToMarkup } from 'mathlive';

	let { latex, label }: { latex: string; label?: string } = $props();

	const markup = $derived(convertLatexToMarkup(latex, { defaultMode: 'math' }));
</script>

<span class="math" role="img" aria-label={label ?? latex}>{@html markup}</span>

<style>
	.math {
		display: inline-block;
	}
</style>
