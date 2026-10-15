<script lang="ts">
	import MathStatic from './MathStatic.svelte';
	import { parseRichText, type Inline, type RichPart } from './rich-text';

	/** Content text with simple Markdown (paragraphs, lists, bold, italic) and inline math. */
	let { parts }: { parts: readonly RichPart[] } = $props();

	const blocks = $derived(parseRichText(parts));
</script>

{#snippet run(inline: Inline)}
	{#if inline.kind === 'math'}
		<MathStatic latex={inline.value} />
	{:else if inline.bold && inline.italic}
		<strong><em>{inline.value}</em></strong>
	{:else if inline.bold}
		<strong>{inline.value}</strong>
	{:else if inline.italic}
		<em>{inline.value}</em>
	{:else}
		{inline.value}
	{/if}
{/snippet}

<div class="rich">
	{#each blocks as block, b (b)}
		{#if block.kind === 'p'}
			<p>{#each block.inlines as inline, i (i)}{@render run(inline)}{/each}</p>
		{:else if block.kind === 'ul'}
			<ul>
				{#each block.items as item, i (i)}
					<li>{#each item as inline, j (j)}{@render run(inline)}{/each}</li>
				{/each}
			</ul>
		{:else}
			<ol start={block.start}>
				{#each block.items as item, i (i)}
					<li>{#each item as inline, j (j)}{@render run(inline)}{/each}</li>
				{/each}
			</ol>
		{/if}
	{/each}
</div>

<style>
	.rich {
		overflow-wrap: anywhere;
	}
	.rich :global(p),
	.rich :global(ul),
	.rich :global(ol) {
		margin: 0 0 0.5rem;
	}
	.rich :global(ul),
	.rich :global(ol) {
		padding-left: 1.5rem;
	}
</style>
