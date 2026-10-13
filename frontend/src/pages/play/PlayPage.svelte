<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import { MAX_ATTEMPTS, feedbackMessage, nextProblem, startSession, submitAnswer } from '../../entities/problem';
	import type { Mastery, Problem } from '../../entities/problem';
	import { fetchMe, logout } from '../../entities/player';
	import type { Player } from '../../entities/player';
	import { ApiError } from '../../shared/api';
	import { PixelButton, PixelFrame } from '../../shared/ui';
	import { MathCard } from '../../widgets/math-card';
	import type { CardFeedback } from '../../widgets/math-card';

	let player = $state<Player | null>(null);
	let sessionId = '';
	let problem = $state<Problem | null>(null);
	let attemptsLeft = $state(MAX_ATTEMPTS);
	let feedback = $state<CardFeedback | null>(null);
	let mastery = $state<Mastery | null>(null);
	let revealedLatex = $state<string | null>(null);
	let finished = $state(false);
	let busy = $state(false);
	let solvedCount = $state(0);
	let loadError = $state('');
	let card: MathCard | undefined = $state();

	function errorText(err: unknown): string {
		if (err instanceof ApiError && err.status === 429) {
			return 'Whoa, slow down! Wait a moment, then try again.';
		}
		if (err instanceof ApiError && err.code === 'network') {
			return "Can't reach the game. Check your internet.";
		}
		return 'Something went wrong. Please try again.';
	}

	function leaveIfSignedOut(err: unknown): boolean {
		if (err instanceof ApiError && err.status === 401) {
			void goto('/');
			return true;
		}
		return false;
	}

	async function loadNext() {
		busy = true;
		try {
			problem = await nextProblem(sessionId);
			attemptsLeft = MAX_ATTEMPTS;
			feedback = null;
			mastery = null;
			revealedLatex = null;
			finished = false;
			loadError = '';
		} catch (err) {
			if (!leaveIfSignedOut(err)) loadError = errorText(err);
		} finally {
			busy = false;
		}
	}

	async function start() {
		loadError = '';
		try {
			player = (await fetchMe()).player;
			sessionId = (await startSession()).session_id;
		} catch (err) {
			if (!leaveIfSignedOut(err)) loadError = errorText(err);
			return;
		}
		await loadNext();
	}

	async function submit(latex: string) {
		if (!problem || busy) return;
		busy = true;
		try {
			const result = await submitAnswer(problem.problem_id, latex);
			mastery = result.mastery;
			attemptsLeft = result.attempts_left;
			if (result.solved) {
				solvedCount += 1;
				feedback = { tone: 'good', text: feedbackMessage(result.verdict, result.misconception) };
				finished = true;
			} else if (result.answer_latex !== null) {
				feedback = { tone: 'info', text: 'Good try! Every mistake helps you learn.' };
				revealedLatex = result.answer_latex;
				finished = true;
			} else {
				const verdict = result.verdict;
				feedback = {
					tone: verdict === 'incorrect' ? 'try' : 'info',
					text: feedbackMessage(verdict, result.misconception)
				};
				if (verdict === 'incorrect') card?.resetInput();
			}
		} catch (err) {
			if (err instanceof ApiError && err.code === 'problem_closed') {
				busy = false;
				await loadNext();
				return;
			}
			if (!leaveIfSignedOut(err)) feedback = { tone: 'info', text: errorText(err) };
		} finally {
			busy = false;
		}
	}

	async function quit() {
		try {
			await logout();
		} catch {
			// Leaving anyway: the session cookie expires on its own.
		}
		await goto('/');
	}

	onMount(() => {
		void start();
	});
</script>

<PixelFrame title="MATH QUEST">
	{#snippet hud()}
		<span data-testid="solved">&#9733; {solvedCount}</span>
		<PixelButton variant="plain" label="Log out" onclick={quit}>Exit</PixelButton>
	{/snippet}

	{#if problem}
		<MathCard
			bind:this={card}
			{problem}
			{attemptsLeft}
			{feedback}
			{mastery}
			{revealedLatex}
			{finished}
			{busy}
			onSubmit={submit}
			onNext={loadNext}
		/>
	{:else if loadError}
		<p class="note" role="alert">{loadError}</p>
		<PixelButton variant="gold" onclick={start}>Try again</PixelButton>
	{:else}
		<p class="note">Getting your quest ready{player ? `, ${player.nickname}` : ''}...</p>
	{/if}
</PixelFrame>

<style>
	.note {
		font-size: 1.2rem;
		text-align: center;
	}
</style>
