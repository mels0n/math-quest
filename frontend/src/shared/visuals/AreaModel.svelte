<script lang="ts">
	import Figure from './Figure.svelte';
	import { areaModel } from './layout';
	import type { AreaModelParams } from './model';

	let { params }: { params: AreaModelParams } = $props();
	const figure = $derived(areaModel(params));
</script>

<Figure {figure} kind="area_model" />
