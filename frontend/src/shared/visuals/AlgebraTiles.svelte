<script lang="ts">
	import Figure from './Figure.svelte';
	import { algebraTiles } from './layout';
	import type { AlgebraTilesParams } from './model';

	let { params }: { params: AlgebraTilesParams } = $props();
	const figure = $derived(algebraTiles(params));
</script>

<Figure {figure} kind="algebra_tiles" />
