<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import { AuthPanel } from '../../features/auth';
	import type { AuthMode } from '../../features/auth';
	import { GradePicker } from '../../features/grade-hint';
	import type { GradeHint } from '../../entities/problem';
	import { fetchMe, logout } from '../../entities/player';
	import type { Player } from '../../entities/player';
	import { PixelButton, PixelFrame } from '../../shared/ui';

	let returning = $state<Player | null>(null);
	let checked = $state(false);
	/** A new player answers the grade question before the placement round. */
	let newPlayer = $state(false);

	onMount(async () => {
		try {
			returning = (await fetchMe()).player;
		} catch {
			returning = null;
		} finally {
			checked = true;
		}
	});

	const play = () => goto('/play');

	function signedIn(_player: Player, mode: AuthMode) {
		if (mode === 'signup') {
			newPlayer = true;
		} else {
			void play();
		}
	}

	const place = (grade: GradeHint | null) => goto(`/placement?grade=${grade ?? 'skip'}`);

	async function switchPlayer() {
		try {
			await logout();
		} catch {
			// The form below still works if the old session lingers.
		}
		returning = null;
	}
</script>

<PixelFrame title="MATH QUEST">
	<p class="lead">Solve puzzles, level up your skills, and master the math world!</p>
	{#if !checked}
		<p class="lead" role="status">Loading...</p>
	{:else if returning}
		<section class="back">
			<p>Welcome back, <strong data-testid="nickname">{returning.nickname}</strong>!</p>
			<PixelButton variant="mint" onclick={play}>Continue</PixelButton>
			<PixelButton variant="plain" onclick={switchPlayer}>Not me</PixelButton>
		</section>
	{:else if newPlayer}
		<GradePicker onPick={(grade) => void place(grade)} />
	{:else}
		<AuthPanel onSignedIn={signedIn} />
	{/if}
</PixelFrame>

<style>
	.lead {
		margin: 0;
		font-size: 1.2rem;
		text-align: center;
	}
	.back {
		display: flex;
		flex-direction: column;
		gap: 1rem;
		align-items: center;
		padding: 1.25rem;
		background: var(--mq-navy);
		border: 4px solid var(--mq-mint);
		font-size: 1.3rem;
	}
	.back p {
		margin: 0;
	}
</style>
