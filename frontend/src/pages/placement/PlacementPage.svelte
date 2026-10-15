<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import { GRADE_HINTS, answerPlacement, startPlacement } from '../../entities/problem';
	import type { Answer, GradeHint, PlacementDone, PlacementStep } from '../../entities/problem';
	import { GradePicker, parseGrade } from '../../features/grade-hint';
	import { ApiError, commonErrorMessage } from '../../shared/api';
	import { PixelButton, PixelFrame, ProgressBar } from '../../shared/ui';
	import { MathCard } from '../../widgets/math-card';
	import type { CardFeedback } from '../../widgets/math-card';
	import { PLACEMENT_COPY, outcomeLines, progressLabel, retryLine } from './placement-copy';

	type Phase = 'checking' | 'grade' | 'probe' | 'done';

	let phase = $state<Phase>('checking');
	let step = $state<PlacementStep | null>(null);
	let done = $state<PlacementDone | null>(null);
	let feedback = $state<CardFeedback | null>(null);
	let busy = $state(false);
	let notice = $state<{ text: string; label: string; action: () => void } | null>(null);
	let retake = $state(false);

	const lines = $derived(done ? outcomeLines(done) : null);
	let doneHeading: HTMLHeadingElement | undefined = $state();

	// Move focus to the result once it is on screen, so it is read out.
	$effect(() => {
		if (phase === 'done' && doneHeading) doneHeading.focus();
	});

	function fail(err: unknown, retry: () => void) {
		if (err instanceof ApiError && err.status === 401) {
			void goto('/');
			return;
		}
		if (err instanceof ApiError && err.code === 'placement_closed') {
			notice = { text: PLACEMENT_COPY.closed, label: PLACEMENT_COPY.again, action: restart };
			return;
		}
		if (err instanceof ApiError && err.code === 'retake_too_soon') {
			notice = { text: PLACEMENT_COPY.tooSoon, label: PLACEMENT_COPY.back, action: () => void goto('/play') };
			return;
		}
		notice = { text: commonErrorMessage(err), label: 'Try again', action: retry };
	}

	function restart() {
		notice = null;
		step = null;
		done = null;
		phase = 'grade';
	}

	async function begin(grade: GradeHint | null) {
		busy = true;
		notice = null;
		try {
			step = await startPlacement(grade);
			feedback = null;
			phase = 'probe';
		} catch (err) {
			fail(err, () => void begin(grade));
		} finally {
			busy = false;
		}
	}

	async function submit(answer: Answer) {
		if (!step || busy) return;
		const asked = step;
		busy = true;
		try {
			const result = await answerPlacement(asked.placement_id, asked.problem.problem_id, answer);
			notice = null;
			if (result.done) {
				done = result;
				step = null;
				phase = 'done';
				return;
			}
			step = result;
			const line = retryLine(result.retry);
			feedback = line ? { tone: 'info', text: line } : null;
		} catch (err) {
			fail(err, () => {
				notice = null;
			});
		} finally {
			busy = false;
		}
	}

	onMount(() => {
		const params = new URL(window.location.href).searchParams;
		retake = params.has('retake');
		const grade = parseGrade(params.get('grade'), GRADE_HINTS);
		if (grade === undefined) {
			phase = 'grade';
		} else {
			void begin(grade);
		}
	});
</script>

<PixelFrame title={PLACEMENT_COPY.title}>
	{#if notice}
		<div class="notice" role="alert">
			<p>{notice.text}</p>
			<PixelButton variant="gold" onclick={notice.action}>{notice.label}</PixelButton>
		</div>
	{/if}

	{#if phase === 'grade'}
		{#if retake}<p class="lead">{PLACEMENT_COPY.retake}</p>{/if}
		<GradePicker disabled={busy} onPick={(grade) => void begin(grade)} />
	{:else if phase === 'probe' && step}
		{#if step.question === 1}<p class="lead">{PLACEMENT_COPY.intro}</p>{/if}
		<!-- The visible count says it; the bar is decoration for screen readers. -->
		<div aria-hidden="true">
			<ProgressBar value={step.question / step.max_questions} label={progressLabel(step)} />
		</div>
		<p class="count" data-testid="placement-count">{progressLabel(step)}</p>
		<MathCard
			problem={step.problem}
			attemptsLeft={0}
			hearts={false}
			{feedback}
			mastery={null}
			revealedLatex={null}
			finished={false}
			{busy}
			onSubmit={submit}
			onNext={() => {}}
		/>
	{:else if phase === 'done' && done && lines}
		<section class="done" data-testid="placement-done">
			<h2 class="mq-pixel" tabindex="-1" bind:this={doneHeading}>{PLACEMENT_COPY.doneTitle}</h2>
			<p>{lines.known}</p>
			<p>{lines.places}</p>
			<PixelButton variant="mint" onclick={() => void goto('/play')}>{PLACEMENT_COPY.start}</PixelButton>
		</section>
	{:else if !notice}
		<p class="lead" role="status">{PLACEMENT_COPY.loading}...</p>
	{/if}
</PixelFrame>

<style>
	.lead {
		margin: 0;
		font-size: 1.2rem;
		text-align: center;
	}
	.count {
		margin: 0;
		font-size: 1rem;
		text-align: center;
	}
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
	.done {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 1rem;
		padding: 1.25rem;
		background: var(--mq-navy);
		border: 4px solid var(--mq-gold);
		text-align: center;
	}
	.done h2:focus:not(:focus-visible) {
		outline: none;
	}
	.done h2 {
		margin: 0;
		font-size: 1rem;
		color: var(--mq-gold);
	}
	.done p {
		margin: 0;
		font-size: 1.25rem;
	}
</style>
