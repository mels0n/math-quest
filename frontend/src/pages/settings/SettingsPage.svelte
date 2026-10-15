<script lang="ts">
	import { goto } from '$app/navigation';
	import { logout } from '../../entities/player';
	import { PixelButton, PixelFrame } from '../../shared/ui';

	async function quit() {
		try {
			await logout();
		} catch {
			// Leaving anyway: the session cookie expires on its own.
		}
		await goto('/');
	}
</script>

<PixelFrame title="SETTINGS">
	<section class="item">
		<h2 class="mq-pixel">STARTING SPOT</h2>
		<p>
			Puzzles too easy or too hard? Take the warm-up again to find a better starting spot. Skills
			you have mastered stay mastered.
		</p>
		<PixelButton variant="gold" onclick={() => void goto('/placement?retake=1')}>
			Retake warm-up
		</PixelButton>
	</section>
	<section class="item">
		<h2 class="mq-pixel">PLAYER</h2>
		<p>Done for now, or someone else's turn?</p>
		<PixelButton variant="plain" onclick={quit}>Log out</PixelButton>
	</section>
	<div class="back">
		<PixelButton variant="mint" onclick={() => void goto('/play')}>Back to play</PixelButton>
	</div>
</PixelFrame>

<style>
	.item {
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		gap: 0.9rem;
		padding: 1.25rem;
		background: var(--mq-navy);
		border: 4px solid var(--mq-mint);
	}
	h2 {
		margin: 0;
		font-size: 0.85rem;
		color: var(--mq-gold);
	}
	p {
		margin: 0;
		font-size: 1.15rem;
		line-height: 1.45;
	}
	.back {
		display: flex;
		justify-content: center;
	}
</style>
