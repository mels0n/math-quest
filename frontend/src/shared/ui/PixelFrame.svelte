<script lang="ts">
	import type { Snippet } from 'svelte';

	let { title, hud, children }: { title: string; hud?: Snippet; children: Snippet } = $props();
</script>

<main class="frame">
	<header class="bar">
		<h1 class="mq-pixel title">{title}</h1>
		{#if hud}<div class="hud mq-pixel">{@render hud()}</div>{/if}
	</header>
	<div class="body">{@render children()}</div>
</main>

<style>
	.frame {
		max-width: 46rem;
		margin: 0 auto;
		min-height: 100dvh;
		padding: 0.75rem;
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}
	.bar {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.75rem;
		padding: 0.75rem 1rem;
		background: var(--mq-navy);
		border: 4px solid var(--mq-gold);
		box-shadow: 0 4px 0 #000;
	}
	.title {
		margin: 0;
		font-size: 0.9rem;
		color: var(--mq-gold);
	}
	.hud {
		font-size: 0.65rem;
		color: var(--mq-mint);
		display: flex;
		gap: 0.75rem;
		align-items: center;
	}
	.body {
		flex: 1;
		display: flex;
		flex-direction: column;
		gap: 1rem;
	}
</style>
