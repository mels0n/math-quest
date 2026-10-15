<script lang="ts">
	import AlgebraTiles from './AlgebraTiles.svelte';
	import AreaModel from './AreaModel.svelte';
	import ArrayGrid from './ArrayGrid.svelte';
	import BaseTen from './BaseTen.svelte';
	import Clock from './Clock.svelte';
	import FractionBars from './FractionBars.svelte';
	import Money from './Money.svelte';
	import NumberLine from './NumberLine.svelte';
	import type { Visual } from './model';

	/** Draws any visual by its kind. */
	let { visual }: { visual: Visual } = $props();
</script>

{#if visual.kind === 'number_line'}
	<NumberLine params={visual.params} />
{:else if visual.kind === 'base_ten'}
	<BaseTen params={visual.params} />
{:else if visual.kind === 'fraction_bars'}
	<FractionBars params={visual.params} />
{:else if visual.kind === 'area_model'}
	<AreaModel params={visual.params} />
{:else if visual.kind === 'algebra_tiles'}
	<AlgebraTiles params={visual.params} />
{:else if visual.kind === 'array'}
	<ArrayGrid params={visual.params} />
{:else if visual.kind === 'clock'}
	<Clock params={visual.params} />
{:else if visual.kind === 'money'}
	<Money params={visual.params} />
{/if}
