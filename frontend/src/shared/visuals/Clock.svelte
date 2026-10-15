<script lang="ts">
	import Figure from './Figure.svelte';
	import { clock } from './layout';
	import type { ClockParams } from './model';

	let { params }: { params: ClockParams } = $props();
	const figure = $derived(clock(params));
</script>

<Figure {figure} kind="clock" />
