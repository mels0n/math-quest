<script lang="ts">
	import { PixelButton } from '../../shared/ui';

	let { word, onDone }: { word: string; onDone: () => void } = $props();
</script>

<section class="panel" aria-labelledby="rw-title">
	<h2 id="rw-title" class="mq-pixel">Write this down!</h2>
	<p>This is your secret recovery word. If you forget your PIN, it gets you back in.</p>
	<p class="word" data-testid="recovery-word">{word}</p>
	<p class="note">You will only see it this one time.</p>
	<PixelButton variant="mint" onclick={onDone}>I wrote it down</PixelButton>
</section>

<style>
	.panel {
		display: flex;
		flex-direction: column;
		gap: 1rem;
		align-items: center;
		text-align: center;
		padding: 1.25rem;
		background: var(--mq-navy);
		border: 4px solid var(--mq-berry);
	}
	h2 {
		margin: 0;
		font-size: 1rem;
		color: var(--mq-berry);
	}
	p {
		margin: 0;
	}
	.word {
		font-family: var(--mq-pixel-font);
		font-size: 1.4rem;
		padding: 1rem 1.25rem;
		color: var(--mq-navy-deep);
		background: var(--mq-gold);
		border: 4px solid var(--mq-navy-deep);
		word-break: break-all;
		user-select: all;
	}
	.note {
		color: var(--mq-line);
	}
</style>
