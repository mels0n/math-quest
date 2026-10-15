<script lang="ts">
	import Figure from './Figure.svelte';
	import { money } from './layout';
	import type { MoneyParams } from './model';

	let { params }: { params: MoneyParams } = $props();
	const figure = $derived(money(params));
</script>

<Figure {figure} kind="money" />
