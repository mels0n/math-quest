<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import {
		MAX_ATTEMPTS,
		PLAY_COPY,
		answerTry,
		feedbackMessage,
		fetchLesson,
		markLessonSeen,
		nextProblem,
		requestExplanation,
		requestHint,
		startSession,
		startTry,
		submitAnswer
	} from '../../entities/problem';
	import type {
		Answer,
		Explanation,
		Feedback,
		Lesson,
		Mastery,
		Problem,
		PromptPart,
		TryProblem
	} from '../../entities/problem';
	import { fetchMe, logout } from '../../entities/player';
	import type { Player } from '../../entities/player';
	import { ERROR_COPY } from '../../shared/api';
	import { PixelButton, PixelFrame } from '../../shared/ui';
	import { LessonView } from '../../widgets/lesson';
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
	let revealedChoice = $state<number | null>(null);
	let finished = $state(false);
	let busy = $state(false);
	/** The saved total from the server, the same on every device. */
	let solvedCount = $state(0);
	let notice = $state<{ text: string; retry: () => Promise<void>; label: string } | null>(null);
	let card: MathCard | undefined = $state();
	/** Help on the problem on screen: feedback on the last miss, hints shown, explanation. */
	let mistake = $state<Feedback | null>(null);
	let hints = $state<PromptPart[][]>([]);
	let explanation = $state<Explanation | null>(null);
	let missed = $state(false);

	/** The lesson on screen: one due before a new skill, or one replayed from a problem. */
	let lesson = $state<Lesson | null>(null);
	let lessonReplay = $state(false);
	let practice = $state<Problem | null>(null);
	let practiceLeft = $state(MAX_ATTEMPTS);
	let practiceFeedback = $state<CardFeedback | null>(null);
	let practiceMistake = $state<Feedback | null>(null);
	let practiceRevealed = $state<string | null>(null);
	let practiceFinished = $state(false);
	let practiceCard: MathCard | undefined = $state();

	/** A practice problem in the shape the math card draws; it is never scored. */
	function asProblem(t: TryProblem): Problem {
		return {
			type: 'problem',
			problem_id: t.try_id,
			skill_id: t.skill_id,
			skill_name: t.skill_name,
			prompt: t.prompt,
			keypad: t.keypad,
			choices: null,
			has_lesson: false,
			hint_levels: 0,
			has_explanations: false
		};
	}

	async function openLesson(skillId: string, replay: boolean) {
		busy = true;
		try {
			const shown = await fetchLesson(skillId);
			practice = null;
			practiceLeft = MAX_ATTEMPTS;
			practiceFeedback = null;
			practiceMistake = null;
			practiceRevealed = null;
			practiceFinished = false;
			lessonReplay = replay;
			lesson = shown;
			notice = null;
			practice = asProblem(await startTry(skillId));
		} catch (err) {
			fail(err, () => openLesson(skillId, replay));
		} finally {
			busy = false;
		}
	}

	async function practiceAnswer(answer: Answer) {
		if (!practice || busy || !('latex' in answer)) return;
		busy = true;
		try {
			const result = await answerTry(practice.problem_id, answer.latex);
			practiceLeft = result.attempts_left;
			practiceMistake = result.solved ? null : result.feedback;
			if (result.solved) {
				practiceFeedback = { tone: 'good', text: feedbackMessage(result.verdict, null) };
				practiceFinished = true;
			} else if (result.answer_latex !== null) {
				practiceFeedback = { tone: 'info', text: PLAY_COPY.revealed };
				practiceRevealed = result.answer_latex;
				practiceFinished = true;
			} else {
				// Feedback from the server replaces the generic verdict line.
				practiceFeedback = result.feedback
					? null
					: {
							tone: result.verdict === 'incorrect' ? 'try' : 'info',
							text: feedbackMessage(result.verdict, result.misconception)
						};
				if (result.verdict === 'incorrect') practiceCard?.resetInput();
			}
		} catch (err) {
			fail(err, dismiss, false, PLAY_COPY.ok);
		} finally {
			busy = false;
		}
	}

	async function finishLesson() {
		if (!lesson) return;
		if (lessonReplay) {
			lesson = null;
			return;
		}
		busy = true;
		try {
			await markLessonSeen(lesson.skill_id);
		} catch (err) {
			busy = false;
			fail(err, finishLesson);
			return;
		}
		busy = false;
		lesson = null;
		await loadNext();
	}

	/** Shows a failure as a notice with a retry; 'reload' means the problem was already closed. */
	function fail(
		err: unknown,
		retry: () => Promise<void>,
		allowReload = false,
		label: string = PLAY_COPY.retry
	): 'handled' | 'reload' {
		const failure = classifyPlayError(err);
		if (failure.kind === 'signed_out') {
			void goto('/');
			return 'handled';
		}
		if (failure.kind === 'reload' && allowReload) return 'reload';
		if (failure.kind === 'ignore') return 'handled';
		notice = {
			text: failure.kind === 'notice' ? failure.text : ERROR_COPY.fallback,
			retry,
			label
		};
		return 'handled';
	}

	async function loadNext() {
		busy = true;
		try {
			const next = await nextProblem(sessionId);
			if (next.type === 'lesson') {
				busy = false;
				problem = null;
				await openLesson(next.skill_id, false);
				return;
			}
			problem = next;
			attemptsLeft = MAX_ATTEMPTS;
			feedback = null;
			mistake = null;
			hints = [];
			explanation = null;
			missed = false;
			mastery = null;
			revealedLatex = null;
			revealedChoice = null;
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
			const me = await fetchMe();
			player = me.player;
			solvedCount = me.total_solved;
			sessionId = (await startSession()).session_id;
		} catch (err) {
			fail(err, start);
			return;
		}
		await loadNext();
	}

	async function submit(answer: Answer) {
		if (!problem || busy) return;
		busy = true;
		try {
			const result = await submitAnswer(problem.problem_id, answer);
			notice = null;
			mastery = result.mastery;
			attemptsLeft = result.attempts_left;
			solvedCount = result.total_solved;
			mistake = result.solved ? null : result.feedback;
			if (result.verdict === 'incorrect') missed = true;
			if (result.solved) {
				feedback = { tone: 'good', text: feedbackMessage(result.verdict, result.misconception) };
				finished = true;
			} else if (result.answer_latex !== null || result.answer_choice !== null) {
				feedback = { tone: 'info', text: PLAY_COPY.revealed };
				revealedLatex = result.answer_latex;
				revealedChoice = result.answer_choice;
				finished = true;
			} else {
				const verdict = result.verdict;
				// Feedback from the server replaces the generic verdict line.
				feedback = result.feedback
					? null
					: {
							tone: verdict === 'incorrect' ? 'try' : 'info',
							text: feedbackMessage(verdict, result.misconception)
						};
				if (verdict === 'incorrect') card?.resetInput();
			}
		} catch (err) {
			if (fail(err, dismiss, true, PLAY_COPY.ok) === 'reload') {
				busy = false;
				await loadNext();
				return;
			}
		} finally {
			busy = false;
		}
	}

	/**
	 * Asks for help on the open problem. A repeat tap while busy is ignored; a problem
	 * already scored or out of hints changes nothing, and a closed one moves on.
	 */
	async function help(kind: 'hint' | 'explain') {
		if (!problem || busy) return;
		const id = problem.problem_id;
		busy = true;
		try {
			if (kind === 'hint') {
				const hint = await requestHint(id);
				if (problem?.problem_id === id) hints = [...hints, hint.text];
			} else {
				const shown = await requestExplanation(id);
				if (problem?.problem_id === id) explanation = shown;
			}
		} catch (err) {
			if (fail(err, dismiss, true, PLAY_COPY.ok) === 'reload') {
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
			<PixelButton variant="gold" onclick={notice.retry}>{notice.label}</PixelButton>
		</div>
	{/if}

	{#if lesson}
		<LessonView {lesson} replay={lessonReplay} {busy} onDone={finishLesson}>
			{#snippet tryIt()}
				{#if practice}
					<MathCard
						bind:this={practiceCard}
						problem={practice}
						attemptsLeft={practiceLeft}
						feedback={practiceFeedback}
						mistakeFeedback={practiceMistake}
						mastery={null}
						revealedLatex={practiceRevealed}
						finished={practiceFinished}
						{busy}
						onSubmit={practiceAnswer}
						onNext={finishLesson}
					/>
				{/if}
			{/snippet}
		</LessonView>
	{/if}
	{#if problem}
		<!-- Kept mounted while a lesson is replayed, so a half-typed answer survives. -->
		<div class="problem" hidden={lesson !== null}>
			<MathCard
				bind:this={card}
				{problem}
				{attemptsLeft}
				{feedback}
				{mastery}
				{revealedLatex}
				{revealedChoice}
				{finished}
				{busy}
				mistakeFeedback={mistake}
				{hints}
				{explanation}
				{missed}
				onSubmit={submit}
				onNext={loadNext}
				onHint={() => help('hint')}
				onExplain={() => help('explain')}
			/>
			{#if problem.has_lesson}
				<div class="replay">
					<PixelButton variant="plain" disabled={busy} onclick={() => problem && openLesson(problem.skill_id, true)}>
						{PLAY_COPY.replayLesson}
					</PixelButton>
				</div>
			{/if}
		</div>
	{:else if !lesson && !notice}
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
	.replay {
		display: flex;
		justify-content: center;
		margin-top: 0.75rem;
	}
	.note {
		font-size: 1.2rem;
		text-align: center;
	}
</style>
