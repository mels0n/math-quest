<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import {
		MAX_ATTEMPTS,
		PLAY_COPY,
		feedbackMessage,
		nextProblem,
		startSession,
		submitAnswer
	} from '../../entities/problem';
	import type { Mastery, Problem } from '../../entities/problem';
	import { fetchMe, logout } from '../../entities/player';
	import type { Player } from '../../entities/player';
		import { ERROR_COPY } from '../../shared/api';
	import { PixelButton, PixelFrame } from '../../shared/ui';
	import { MathCard } from '../../widgets/math-card';
	import type { CardFeedback } from '../../widgets/math-card';
	import { classifyPlayError } from './errors';

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
	let notice = $state<{ text: string; retry: () => Promise<void> } | null>(null);
	let card: MathCard | undefined = $state();

	/** Shows a failure as a notice with a retry; 'reload' means the problem was already closed. */
	function fail(
		err: unknown,
		retry: () => Promise<void>,
		allowReload = false
	): 'handled' | 'reload' {
		const failure = classifyPlayError(err);
		if (failure.kind === 'signed_out') {
			void goto('/');
			return 'handled';
		}
		if (failure.kind === 'reload' && allowReload) return 'reload';
		notice = {
			text: failure.kind === 'notice' ? failure.text : ERROR_COPY.fallback,
			retry
		};
		return 'handled';
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
			notice = null;
		} catch (err) {
			fail(err, loadNext);
		} finally {
			busy = false;
		}
	}

	async function start() {
		notice = null;
		try {
			player = (await fetchMe()).player;
			sessionId = (await startSession()).session_id;
		} catch (err) {
			fail(err, start);
			return;
		}
		await loadNext();
	}

	async function submit(latex: string) {
		if (!problem || busy) return;
		busy = true;
		try {
			const result = await submitAnswer(problem.problem_id, latex);
			notice = null;
			mastery = result.mastery;
			attemptsLeft = result.attempts_left;
			if (result.solved) {
				solvedCount += 1;
				feedback = { tone: 'good', text: feedbackMessage(result.verdict, result.misconception) };
				finished = true;
			} else if (result.answer_latex !== null) {
				feedback = { tone: 'info', text: PLAY_COPY.revealed };
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
			if (fail(err, dismiss, true) === 'reload') {
				busy = false;
				await loadNext();
				return;
			}
		} finally {
			busy = false;
		}
	}

	async function dismiss() {
		notice = null;
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
		<PixelButton variant="plain" label="Log out" onclick={quit}>Log out</PixelButton>
	{/snippet}

	{#if notice}
		<div class="notice" role="alert">
			<p>{notice.text}</p>
			<PixelButton variant="gold" onclick={notice.retry}>{PLAY_COPY.retry}</PixelButton>
		</div>
	{/if}

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
	{:else if !notice}
		<p class="note">{PLAY_COPY.loading}{player ? `, ${player.nickname}` : ''}...</p>
	{/if}
</PixelFrame>

<style>
	.notice {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.75rem;
		padding: 1rem;
		background: var(--mq-berry);
		border: 4px solid var(--mq-navy-deep);
	}
	.notice p {
		margin: 0;
		font-size: 1.2rem;
		font-weight: 600;
	}
	.note {
		font-size: 1.2rem;
		text-align: center;
	}
</style>
