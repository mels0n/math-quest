<script lang="ts">
	import { onMount, tick } from 'svelte';
	import { ApiError } from '../../shared/api';
	import { MathStatic, PromptView, RichText } from '../../shared/ui';
	import {
		MAX_PREVIEW_SEED,
		adminErrorMessage,
		coverageCell,
		getContent,
		getSkillPreview,
		parseSeed,
		stuckLogUrl
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
	let targets = $state<Record<string, string>>({});
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
			const overview = await getContent();
			packs = overview.packs;
			targets = overview.targets;
		} catch (err) {
			if (!onSessionLost(err)) loadError = adminErrorMessage(err);
		} finally {
			loading = false;
		}
	});

	async function open(skillId: string, focus = false) {
		const seed = parseSeed(seedText);
		if (seed === null) {
			previewError = `The seed is a whole number from 0 to ${MAX_PREVIEW_SEED}, or blank.`;
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

	/** The coverage cells of a row, each with the gap field that marks it short. */
	function cells(skill: SkillCoverage) {
		const t = (field: string) => targets[field];
		return [
			{ label: 'Tiers', field: 'tiers', text: coverageCell(skill.tiers, t('tiers')) },
			{
				label: 'Mistakes',
				field: 'misconceptions',
				text: coverageCell(skill.misconceptions, t('misconceptions'))
			},
			{
				label: 'Feedback',
				field: 'misconception feedback',
				text: coverageCell(skill.feedback, String(skill.misconceptions))
			},
			{
				label: 'Word',
				field: 'word templates',
				text: coverageCell(skill.word_templates, t('word templates'))
			},
			{ label: 'Bank', field: 'bank items', text: coverageCell(skill.bank_items, t('bank items')) },
			{ label: 'Lesson', field: 'lesson', text: skill.lesson ? 'yes' : 'no' },
			{ label: 'Hints', field: 'hints', text: coverageCell(skill.hints, t('hints')) },
			{
				label: 'Explain',
				field: 'explanations',
				text: coverageCell(skill.explanations, t('explanations'))
			}
		];
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
							<th>Feedback</th>
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
								{#each cells(skill) as cell (cell.label)}
									<td data-label={cell.label} class:short={shortOf(skill, cell.field)}
										>{cell.text}</td
									>
								{/each}
								<td data-label="Status">{status(skill)}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			{/if}
		{/each}
	{/each}
	<h3>Stuck log</h3>
	<p class="muted">
		Problems a player still missed after seeing every explanation of the skill. No player
		names are included. Pass the JSON file to <code>content-report --stuck</code>.
	</p>
	<p class="downloads">
		<a href={stuckLogUrl('json')} download="stuck-log.json">Download JSON</a>
		<a href={stuckLogUrl('csv')} download="stuck-log.csv">Download CSV</a>
	</p>
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
					<input type="text" inputmode="numeric" maxlength="16" bind:value={seedText} />
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
		min-height: 2.75rem;
		text-align: left;
	}
	select {
		width: 100%;
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
	.downloads {
		display: flex;
		flex-wrap: wrap;
		gap: 1rem;
	}
</style>
