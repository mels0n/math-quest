<script lang="ts">
	import type { Snippet } from 'svelte';

	let {
		variant = 'gold',
		type = 'button',
		disabled = false,
		label,
		onclick,
		children
	}: {
		variant?: 'gold' | 'mint' | 'berry' | 'plain';
		type?: 'button' | 'submit';
		disabled?: boolean;
		label?: string;
		onclick?: () => void;
		children: Snippet;
	} = $props();
</script>

<button class="btn {variant}" {type} {disabled} aria-label={label} {onclick}>
	{@render children()}
</button>

<style>
	.btn {
		min-width: var(--mq-tap);
		min-height: var(--mq-tap);
		padding: 0.5rem 1.1rem;
		font-family: var(--mq-pixel-font);
		font-size: 0.85rem;
		color: var(--mq-navy-deep);
		border: 4px solid var(--mq-navy-deep);
		border-radius: var(--mq-radius);
		box-shadow: 0 4px 0 #000;
		cursor: pointer;
		touch-action: manipulation;
	}
	.gold {
		background: var(--mq-gold);
	}
	.mint {
		background: var(--mq-mint);
	}
	.berry {
		background: var(--mq-berry);
		color: #fff;
	}
	.plain {
		background: var(--mq-navy);
		color: #fff;
		border-color: var(--mq-line);
	}
	.btn:active:not(:disabled) {
		transform: translateY(3px);
		box-shadow: 0 1px 0 #000;
	}
	.btn:focus-visible {
		outline: none;
		box-shadow:
			var(--mq-focus),
			0 4px 0 #000;
	}
	.btn:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}
</style>
