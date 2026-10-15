<script lang="ts">
	import { tick, type Snippet } from 'svelte';
	import type { Lesson } from '../../entities/problem';
	import { PixelButton, PromptView } from '../../shared/ui';
	import { VisualView } from '../../shared/visuals';
	import { LESSON_COPY, lessonSteps } from './steps';
	import type { LessonStep } from './steps';

	/**
	 * A lesson: its screens with Back and Next, the worked example revealed one step at a
	 * time, then the try-it (drawn by the caller through `tryIt`) and a button to finish.
	 */
	let {
		lesson,
		tryIt,
		replay = false,
		busy = false,
		onDone
	}: {
		lesson: Lesson;
		tryIt: Snippet;
		replay?: boolean;
		busy?: boolean;
		onDone: () => void;
	} = $props();

	const steps = $derived(lessonSteps(lesson.screens.length));
	let at = $state(0);
	let shownSteps = $state(1);
	const step = $derived<LessonStep>(steps[Math.min(at, steps.length - 1)] ?? { kind: 'try' });
	const workedDone = $derived(shownSteps >= lesson.worked_example.steps.length);
	let heading: HTMLElement | undefined = $state();

	$effect(() => {
		void lesson.skill_id;
		at = 0;
		shownSteps = 1;
	});

	let stepList: HTMLElement | undefined = $state();
	let nav: HTMLElement | undefined = $state();

	/** Shows the next worked step and moves focus to it, or to Next after the last one. */
	async function showStep() {
		shownSteps += 1;
		await tick();
		if (shownSteps >= lesson.worked_example.steps.length) {
			const buttons = nav?.querySelectorAll('button');
			buttons?.[buttons.length - 1]?.focus();
		} else {
			stepList?.querySelector<HTMLElement>('li:last-child')?.focus();
		}
	}

	function go(to: number) {
		at = Math.max(0, Math.min(steps.length - 1, to));
		// Move focus to the new page's heading so screen readers read it.
		queueMicrotask(() => heading?.focus());
	}
</script>

<section class="lesson" aria-label="Lesson: {lesson.skill_name}" data-testid="lesson">
	<div class="top">
		<span class="skill">{lesson.skill_name}</span>
		<span class="count" data-testid="lesson-count">{LESSON_COPY.screenOf(at + 1, steps.length)}</span>
		<ol class="dots" aria-hidden="true">
			{#each steps as _, i (i)}
				<li class:on={i === at} class:past={i < at}></li>
			{/each}
		</ol>
	</div>

	{#if step.kind === 'screen'}
		{@const screen = lesson.screens[step.index]}
		{#if screen}
			<h2 class="title" tabindex="-1" bind:this={heading}>{screen.title}</h2>
			<div class="body" data-testid="lesson-body"><PromptView parts={screen.body} /></div>
			{#if screen.visual}
				<div class="visual"><VisualView visual={screen.visual} /></div>
			{/if}
		{/if}
	{:else if step.kind === 'worked'}
		<h2 class="title" tabindex="-1" bind:this={heading}>{LESSON_COPY.worked}</h2>
		<div class="worked-prompt"><PromptView parts={lesson.worked_example.prompt} /></div>
		<ol class="worked-steps" data-testid="worked-steps" bind:this={stepList}>
			{#each lesson.worked_example.steps.slice(0, shownSteps) as parts, i (i)}
				<li tabindex="-1"><PromptView {parts} /></li>
			{/each}
		</ol>
		{#if !workedDone}
			<div class="center">
				<PixelButton variant="gold" onclick={showStep}>{LESSON_COPY.nextStep}</PixelButton>
			</div>
		{/if}
	{:else}
		<h2 class="title" tabindex="-1" bind:this={heading}>{LESSON_COPY.tryIt}</h2>
		<div class="try" data-testid="lesson-try">{@render tryIt()}</div>
	{/if}

	<div class="nav" bind:this={nav}>
		<PixelButton variant="plain" disabled={at === 0 || busy} onclick={() => go(at - 1)}>
			{LESSON_COPY.back}
		</PixelButton>
		{#if step.kind === 'try'}
			<PixelButton variant="mint" disabled={busy} onclick={onDone}>
				{replay ? LESSON_COPY.doneReplay : LESSON_COPY.done}
			</PixelButton>
		{:else}
			<PixelButton
				variant="mint"
				disabled={busy || (step.kind === 'worked' && !workedDone)}
				onclick={() => go(at + 1)}
			>
				{LESSON_COPY.next}
			</PixelButton>
		{/if}
	</div>
</section>

<style>
	.lesson {
		display: flex;
		flex-direction: column;
		gap: 0.9rem;
		padding: 1.1rem;
		min-width: 0;
		color: var(--mq-ink);
		background: var(--mq-card);
		border: 4px solid var(--mq-mint);
		border-radius: var(--mq-radius);
		font-family: var(--mq-sans-font);
	}
	.top {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 0.5rem;
		flex-wrap: wrap;
	}
	.skill {
		font-weight: 700;
		color: var(--mq-ink-soft);
	}
	.count {
		font-size: 0.95rem;
		color: var(--mq-ink-soft);
	}
	.worked-steps li {
		outline: none;
	}
	.worked-steps li:focus-visible {
		outline: 3px solid var(--mq-gold);
	}
	.dots {
		display: flex;
		gap: 0.4rem;
		margin: 0;
		padding: 0;
		list-style: none;
	}
	.dots li {
		width: 0.7rem;
		height: 0.7rem;
		background: var(--mq-line);
		border: 2px solid var(--mq-navy);
	}
	.dots li.past {
		background: var(--mq-mint);
	}
	.dots li.on {
		background: var(--mq-gold);
	}
	.title {
		margin: 0;
		font-size: 0.85rem;
		color: var(--mq-navy);
		outline: none;
	}
	.body,
	.worked-steps {
		font-size: 1.25rem;
		line-height: 1.45;
	}
	.body :global(.text),
	.worked-steps :global(.text) {
		white-space: pre-line;
	}
	.worked-prompt {
		font-size: 2rem;
		text-align: center;
	}
	.worked-steps {
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
		margin: 0;
		padding-left: 1.5rem;
	}
	.visual {
		min-width: 0;
	}
	.center {
		display: flex;
		justify-content: center;
	}
	.nav {
		display: flex;
		justify-content: space-between;
		gap: 0.75rem;
		flex-wrap: wrap;
	}
	@media (max-width: 380px) {
		.lesson {
			padding: 0.75rem;
		}
	}
</style>
