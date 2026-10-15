<script lang="ts">
	import Figure from './Figure.svelte';
	import { numberLine } from './layout';
	import type { NumberLineParams } from './model';

	let { params }: { params: NumberLineParams } = $props();
	const figure = $derived(numberLine(params));
</script>

<Figure {figure} kind="number_line" />
