<script lang="ts">
	import Figure from './Figure.svelte';
	import { baseTen } from './layout';
	import type { BaseTenParams } from './model';

	let { params }: { params: BaseTenParams } = $props();
	const figure = $derived(baseTen(params));
</script>

<Figure {figure} kind="base_ten" />
