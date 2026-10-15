<script lang="ts">
	import Figure from './Figure.svelte';
	import { arrayGrid } from './layout';
	import type { ArrayParams } from './model';

	let { params }: { params: ArrayParams } = $props();
	const figure = $derived(arrayGrid(params));
</script>

<Figure {figure} kind="array" />
