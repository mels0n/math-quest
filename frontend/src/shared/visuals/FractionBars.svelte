<script lang="ts">
	import Figure from './Figure.svelte';
	import { fractionBars } from './layout';
	import type { FractionBarsParams } from './model';

	let { params }: { params: FractionBarsParams } = $props();
	const figure = $derived(fractionBars(params));
</script>

<Figure {figure} kind="fraction_bars" />
