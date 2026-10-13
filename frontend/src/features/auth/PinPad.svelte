<script lang="ts">
	import { PIN_LENGTH, createPinEntry } from './pin';

	let { onComplete }: { onComplete: (pin: string) => void } = $props();

	let filled = $state(0);
	const entry = createPinEntry((pin) => onComplete(pin));

	function press(digit: string) {
		entry.press(digit);
		filled = entry.value().length;
	}
	function back() {
		entry.backspace();
		filled = entry.value().length;
	}
	function clear() {
		entry.clear();
		filled = 0;
	}
</script>

<div class="pad" role="group" aria-label="PIN pad">
	<div class="dots" aria-live="polite" aria-label="{filled} of {PIN_LENGTH} numbers entered">
		{#each Array.from({ length: PIN_LENGTH }, (_, i) => i) as i (i)}
			<span class="dot" class:on={i < filled}></span>
		{/each}
	</div>
	<div class="keys">
		{#each ['1', '2', '3', '4', '5', '6', '7', '8', '9'] as d (d)}
			<button type="button" class="key" onclick={() => press(d)}>{d}</button>
		{/each}
		<button type="button" class="key aux" aria-label="Clear" onclick={clear}>C</button>
		<button type="button" class="key" onclick={() => press('0')}>0</button>
		<button type="button" class="key aux" aria-label="Delete last number" onclick={back}>
			&larr;
		</button>
	</div>
</div>

<style>
	.pad {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.75rem;
	}
	.dots {
		display: flex;
		gap: 0.75rem;
	}
	.dot {
		width: 1.4rem;
		height: 1.4rem;
		border: 3px solid var(--mq-gold);
		background: var(--mq-navy-deep);
	}
	.dot.on {
		background: var(--mq-gold);
	}
	.keys {
		display: grid;
		grid-template-columns: repeat(3, minmax(var(--mq-tap), 4.5rem));
		gap: 0.5rem;
	}
	.key {
		min-height: var(--mq-tap);
		font-family: var(--mq-pixel-font);
		font-size: 1.1rem;
		color: #fff;
		background: var(--mq-navy);
		border: 4px solid var(--mq-line);
		border-radius: var(--mq-radius);
		box-shadow: 0 4px 0 #000;
		touch-action: manipulation;
		cursor: pointer;
	}
	.key.aux {
		color: var(--mq-gold);
	}
	.key:active {
		transform: translateY(3px);
		box-shadow: 0 1px 0 #000;
	}
	.key:focus-visible {
		outline: none;
		box-shadow: var(--mq-focus);
	}
</style>
