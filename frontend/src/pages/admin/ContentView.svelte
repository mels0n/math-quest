<script lang="ts">
	import { onMount, tick } from 'svelte';
	import { ApiError } from '../../shared/api';
	import { MathStatic, PromptView, RichText } from '../../shared/ui';
	import {
		adminErrorMessage,
		coverageCell,
		getContent,
		getSkillPreview,
		parseSeed
	} from '../../entities/admin';
	import type {
		ContentPack,
		ProblemPreview,
		SkillCoverage,
		SkillPreview
	} from '../../entities/admin';

	/** Called with a failed request; returns true when it ended the admin session. */
	let { onSessionLost }: { onSessionLost: (err: unknown) => boolean } = $props();

	let packs = $state<ContentPack[]>([]);
	let loadError = $state('');
	let loading = $state(true);

	let preview = $state<SkillPreview | null>(null);
	let previewError = $state('');
	let previewBusy = $state(false);
	let seedText = $state('');
	let tier = $state(0);
	let seq = 0;
	let detail: HTMLElement | undefined = $state();

	onMount(async () => {
		try {
			packs = (await getContent()).packs;
		} catch (err) {
			if (!onSessionLost(err)) loadError = adminErrorMessage(err);
		} finally {
			loading = false;
		}
	});

	async function open(skillId: string, focus = false) {
		const seed = parseSeed(seedText);
		if (seed === null) {
			previewError = 'The seed is a whole number from 0 to 2147483647, or blank.';
			return;
		}
		const mine = ++seq;
		previewBusy = true;
		previewError = '';
		try {
			const result = await getSkillPreview(skillId, { seed, tier });
			if (mine !== seq) return;
			preview = result;
			if (focus) {
				await tick();
				detail?.focus();
			}
		} catch (err) {
			if (mine !== seq) return;
			if (err instanceof ApiError && err.status === 422) {
				previewError = 'That tier or seed is not valid for this skill.';
			} else if (!onSessionLost(err)) previewError = adminErrorMessage(err);
		} finally {
			if (mine === seq) previewBusy = false;
		}
	}

	function choose(skill: SkillCoverage) {
		if (preview?.skill_id !== skill.skill_id) tier = 0;
		void open(skill.skill_id, true);
	}

	function resample() {
		if (!preview) return;
		seedText = String(Math.floor(Math.random() * 1_000_000));
		void open(preview.skill_id);
	}

	function status(skill: SkillCoverage): string {
		const gaps = skill.gaps.length;
		return gaps === 0 ? 'done' : gaps === 1 ? '1 gap' : `${gaps} gaps`;
	}

	function shortOf(skill: SkillCoverage, field: string): boolean {
		return skill.gaps.some((g) => g.field === field);
	}

	function params(value: Record<string, unknown>): string {
		return JSON.stringify(value);
	}
</script>

{#snippet answer(problem: ProblemPreview)}
	{#if problem.error}
		<p class="error">Seed {problem.seed}: {problem.error}</p>
	{:else}
		<div class="problem">
			<span class="tag">seed {problem.seed}</span>
			<PromptView parts={problem.prompt} />
			{#if problem.choices}
				<ol class="choices" start="0">
					{#each problem.choices as choice, i (i)}
						<li class:right={i === problem.correct_choice}>
							<PromptView parts={choice} />
							{#if i === problem.correct_choice}<span class="tag ok">answer</span>{/if}
						</li>
					{/each}
				</ol>
			{:else if problem.answer_latex !== null}
				<p class="answer">Answer: <MathStatic latex={problem.answer_latex} /></p>
			{/if}
		</div>
	{/if}
{/snippet}

<section class="card stack" aria-label="Content">
	<h2>Content</h2>
	{#if loading}
		<p class="muted">Loading...</p>
	{:else if loadError}
		<p class="error" role="alert">{loadError}</p>
	{/if}
	{#each packs as pack (pack.id)}
		<p class="live">
			{#if pack.live}<span class="tag ok">live</span>{/if}
			<strong>{pack.title}</strong> ({pack.id}) version <strong>{pack.version}</strong>
		</p>
		{#each pack.regions as region (region.region_id)}
			<h3>
				{region.name}
				<span class="tag">{region.complete ? 'declared complete' : 'in progress'}</span>
			</h3>
			{#if region.skills.length === 0}
				<p class="muted">No skills yet.</p>
			{:else}
				<table class="coverage">
					<thead>
						<tr>
							<th>Skill</th>
							<th>Tiers</th>
							<th>Mistakes</th>
							<th>Word</th>
							<th>Bank</th>
							<th>Lesson</th>
							<th>Hints</th>
							<th>Explain</th>
							<th>Status</th>
						</tr>
					</thead>
					<tbody>
						{#each region.skills as skill (skill.skill_id)}
							<tr>
								<td>
									<button
										type="button"
										class="link"
										aria-label="Preview {skill.name}"
										onclick={() => choose(skill)}>{skill.name}</button
									>
									<span class="muted id">{skill.skill_id}</span>
								</td>
								<td data-label="Tiers" class:short={shortOf(skill, 'tiers')}
									>{coverageCell(skill.tiers, 3)}</td
								>
								<td data-label="Mistakes" class:short={shortOf(skill, 'misconceptions')}
									>{coverageCell(skill.misconceptions, 2)}</td
								>
								<td data-label="Word" class:short={shortOf(skill, 'word templates')}
									>{coverageCell(skill.word_templates, 15)}</td
								>
								<td data-label="Bank" class:short={shortOf(skill, 'bank items')}
									>{coverageCell(skill.bank_items, 30)}</td
								>
								<td data-label="Lesson" class:short={!skill.lesson}>{skill.lesson ? 'yes' : 'no'}</td>
								<td data-label="Hints" class:short={shortOf(skill, 'hints')}
									>{coverageCell(skill.hints, 3)}</td
								>
								<td data-label="Explain" class:short={shortOf(skill, 'explanations')}
									>{coverageCell(skill.explanations, 3)}</td
								>
								<td data-label="Status">{status(skill)}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			{/if}
		{/each}
	{/each}
</section>

{#if preview || previewError || previewBusy}
	<section
		class="card stack"
		aria-label="Skill preview"
		aria-busy={previewBusy}
		tabindex="-1"
		bind:this={detail}
	>
		{#if preview}
			{@const p = preview}
			<h2>{p.name} <span class="muted id">{p.skill_id}</span></h2>
			<p class="muted">
				Grade {p.grade_band}, keypad {p.keypad}, seeds {p.seeds.join(', ')}
			</p>
			<form
				class="row"
				onsubmit={(e) => {
					e.preventDefault();
					void open(p.skill_id);
				}}
			>
				<label>
					Tier
					<select bind:value={tier}>
						{#each p.tier_labels as label, i (i)}
							<option value={i}>{i}: {label}</option>
						{/each}
					</select>
				</label>
				<label class="grow">
					Seed (blank for samples)
					<input type="text" inputmode="numeric" maxlength="10" bind:value={seedText} />
				</label>
				<button type="submit" disabled={previewBusy}>Show</button>
				<button type="button" class="ghost" disabled={previewBusy} onclick={resample}
					>Resample</button
				>
			</form>
			{#if previewError}<p class="error" role="alert">{previewError}</p>{/if}
			{#each p.errors as message, i (i)}<p class="error">{message}</p>{/each}

			<h3>Generated problems</h3>
			{#each p.problems as problem, i (i)}
				{@render answer(problem)}
				{#if problem.misconceptions.length > 0}
					<ul class="mistakes">
						{#each problem.misconceptions as m (m.key)}
							<li>
								<strong>{m.key}</strong> gives <MathStatic latex={m.answer_latex} />
								{#if m.feedback}<RichText parts={m.feedback} />{:else}<span class="muted">
										(no feedback written)</span
									>{/if}
							</li>
						{/each}
					</ul>
				{/if}
			{/each}

			<h3>Lesson</h3>
			{#if p.lesson}
				{#each p.lesson.screens as screen, i (i)}
					<div class="item">
						<h4>{i + 1}. {screen.title}</h4>
						<RichText parts={screen.body} />
						{#if screen.visual}
							<p class="muted">Visual: {screen.visual.kind} {params(screen.visual.params)}</p>
						{/if}
					</div>
				{/each}
				<div class="item">
					<h4>Worked example</h4>
					<PromptView parts={p.lesson.worked_prompt} />
					<ol>
						{#each p.lesson.worked_steps as step, i (i)}<li><RichText parts={step} /></li>{/each}
					</ol>
					<p class="muted">
						Try it: tier {p.lesson.try_it_tier}{p.lesson.try_it_seed !== null
							? `, seed ${p.lesson.try_it_seed}`
							: ''}
					</p>
				</div>
			{:else}
				<p class="muted">No lesson written.</p>
			{/if}

			<h3>Hints (for seed {p.seeds[0]})</h3>
			{#if p.hints}
				<ol>
					{#each p.hints as hint, i (i)}<li><RichText parts={hint} /></li>{/each}
				</ol>
			{:else}
				<p class="muted">No hints written.</p>
			{/if}

			<h3>Explanations (for seed {p.seeds[0]})</h3>
			{#if p.explanations}
				{#each p.explanations as approach, i (i)}
					<div class="item">
						<h4>{approach.style}</h4>
						<RichText parts={approach.body} />
						{#if approach.visual}
							<p class="muted">Visual: {approach.visual.kind} {params(approach.visual.params)}</p>
						{/if}
					</div>
				{/each}
			{:else}
				<p class="muted">No explanations written.</p>
			{/if}

			<h3>Word problems ({p.word_templates.length})</h3>
			{#each p.word_templates as template (template.id)}
				<div class="item">
					<h4>
						{template.id}
						<span class="tag">grade {template.grade_band}</span>
						{#if template.answer_from === 'expression'}<span class="tag">own answer</span>{/if}
					</h4>
					{#each template.samples as sample, i (i)}{@render answer(sample)}{/each}
				</div>
			{:else}
				<p class="muted">No word problems.</p>
			{/each}

			<h3>Bank items ({p.bank_items.length})</h3>
			{#each p.bank_items as item (item.id)}
				<div class="item">
					<h4>{item.id} <span class="tag">{item.kind}</span></h4>
					{@render answer(item.sample)}
				</div>
			{:else}
				<p class="muted">No bank items.</p>
			{/each}
		{:else if previewBusy}
			<p class="muted">Loading...</p>
		{:else if previewError}
			<p class="error" role="alert">{previewError}</p>
		{/if}
	</section>
{/if}

<style>
	h3 {
		font-size: 1rem;
		margin: 0.5rem 0 0;
	}
	h4 {
		font-size: 0.95rem;
		margin: 0 0 0.25rem;
	}
	.live {
		margin: 0;
	}
	.id {
		font-size: 0.8rem;
		display: block;
	}
	h2 .id {
		display: inline;
	}
	table {
		width: 100%;
		border-collapse: collapse;
	}
	th,
	td {
		text-align: left;
		padding: 0.375rem 0.5rem;
		border-bottom: 1px solid var(--mq-line);
	}
	td.short {
		color: #b0123a;
		font-weight: 600;
	}
	button.link {
		background: none;
		border: none;
		color: var(--mq-navy);
		text-decoration: underline;
		padding: 0;
		min-height: 2rem;
		text-align: left;
	}
	select {
		font: inherit;
		min-height: 2.5rem;
		padding: 0.25rem 0.5rem;
	}
	.item,
	.problem {
		border-left: 3px solid var(--mq-line);
		padding: 0.25rem 0 0.25rem 0.75rem;
		margin: 0.25rem 0;
	}
	.answer {
		margin: 0.25rem 0 0;
	}
	.choices li.right {
		font-weight: 700;
	}
	.tag.ok {
		background: #dff7ee;
	}
	.mistakes {
		margin: 0 0 0.5rem;
	}
	ol,
	ul {
		padding-left: 1.5rem;
	}
	@media (max-width: 40rem) {
		.coverage thead {
			display: none;
		}
		.coverage tr {
			display: grid;
			grid-template-columns: repeat(2, minmax(0, 1fr));
			border-bottom: 1px solid var(--mq-line);
			padding: 0.25rem 0;
		}
		.coverage td {
			display: block;
			border: none;
			padding: 0.125rem 0.25rem;
		}
		.coverage td:first-child {
			grid-column: 1 / -1;
		}
		.coverage td[data-label]::before {
			content: attr(data-label) ': ';
			font-weight: 600;
		}
	}
</style>
