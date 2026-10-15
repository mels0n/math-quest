<script lang="ts">
	import type { SkillList } from '../../entities/problem';
	import { PixelButton } from '../../shared/ui';
	import { PICKER_COPY, STATE_LABELS, groupByRegion, hasWeakSpots, lockedLine, practiceLabel } from './picker';

	let {
		list,
		disabled = false,
		onPractice,
		onLesson,
		onWeakSpots
	}: {
		list: SkillList;
		disabled?: boolean;
		onPractice: (skillId: string) => void;
		onLesson: (skillId: string) => void;
		onWeakSpots: () => void;
	} = $props();

	const groups = $derived(groupByRegion(list));
	const weak = $derived(hasWeakSpots(list));
</script>

<section class="weak">
	<PixelButton variant="gold" disabled={disabled || !weak} onclick={onWeakSpots}>
		{PICKER_COPY.weakSpots}
	</PixelButton>
	<p>{weak ? PICKER_COPY.weakSpotsWhy : PICKER_COPY.noWeakSpots}</p>
</section>

{#each groups as group (group.id)}
	<details class="region" open={group.open} data-testid="region-{group.id}">
		<summary class="mq-pixel"><span>{group.name}</span></summary>
		<ul>
			{#each group.skills as skill (skill.skill_id)}
				{@const label = STATE_LABELS[skill.state]}
				<li class="row" data-testid="skill-{skill.skill_id}">
					<button
						type="button"
						class="card"
						aria-label={practiceLabel(skill)}
						{disabled}
						onclick={() => onPractice(skill.skill_id)}
					>
						<span class="name">{skill.name}</span>
						<span class="state state-{skill.state}">
							<span aria-hidden="true">{label.icon}</span>
							{label.text}
						</span>
						{#if skill.state === 'learning'}
							<span class="bar" aria-hidden="true">
								<span class="fill" style:width="{Math.round(Math.min(1, Math.max(0, skill.progress)) * 100)}%"
								></span>
							</span>
						{/if}
					</button>
					{#if skill.has_lesson}
						<button
							type="button"
							class="lesson"
							aria-label="{PICKER_COPY.lesson}: {skill.name}"
							title={PICKER_COPY.lesson}
							{disabled}
							onclick={() => onLesson(skill.skill_id)}
						>
							<svg viewBox="0 0 24 24" width="24" height="24" aria-hidden="true" focusable="false">
								<path
									fill="none"
									stroke="currentColor"
									stroke-width="2.5"
									stroke-linejoin="round"
									d="M3 5.5c3-1.5 6-1.5 9 0v14c-3-1.5-6-1.5-9 0zM12 5.5c3-1.5 6-1.5 9 0v14c-3-1.5-6-1.5-9 0z"
								/>
							</svg>
						</button>
					{/if}
				</li>
			{/each}
			{#if group.locked > 0}
				<li class="locked"><span aria-hidden="true">{STATE_LABELS.locked.icon}</span> {lockedLine(group.locked)}</li>
			{/if}
		</ul>
	</details>
{/each}

<style>
	.weak {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.5rem;
		text-align: center;
	}
	.weak p {
		margin: 0;
		font-size: 1.05rem;
	}
	.region {
		background: var(--mq-navy);
		border: 4px solid var(--mq-mint);
	}
	summary {
		min-height: 44px;
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem;
		list-style: none;
		padding: 0.5rem 0.75rem;
		font-size: 0.75rem;
		line-height: 1.5;
		color: var(--mq-gold);
		cursor: pointer;
	}
	summary::-webkit-details-marker {
		display: none;
	}
	summary::after {
		content: '+';
		font-size: 1rem;
		color: var(--mq-mint);
	}
	.region[open] > summary::after {
		content: '\2212';
	}
	summary:focus-visible {
		outline: none;
		box-shadow: var(--mq-focus);
	}
	ul {
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
		margin: 0;
		padding: 0 0.5rem 0.5rem;
		list-style: none;
	}
	.row {
		display: flex;
		gap: 0.4rem;
		align-items: stretch;
	}
	.card {
		flex: 1;
		min-width: 0;
		min-height: 44px;
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		gap: 0.1rem;
		padding: 0.3rem 0.6rem;
		font: inherit;
		text-align: left;
		color: var(--mq-ink);
		background: var(--mq-card);
		border: 3px solid var(--mq-navy-deep);
		border-radius: var(--mq-radius);
		cursor: pointer;
	}
	.card:focus-visible,
	.lesson:focus-visible {
		outline: none;
		box-shadow: var(--mq-focus);
	}
	.name {
		font-size: 1.05rem;
		font-weight: 700;
		overflow-wrap: anywhere;
	}
	.state {
		font-size: 0.9rem;
		line-height: 1.25;
		color: var(--mq-ink-soft);
	}
	.state-mastered,
	.state-provisional {
		color: #047857;
	}
	.state-review_due {
		color: #9a3412;
	}
	.bar {
		display: block;
		width: 100%;
		height: 0.5rem;
		margin-top: 0.15rem;
		background: #d9dbe7;
		border-radius: var(--mq-radius);
		overflow: hidden;
	}
	.fill {
		display: block;
		height: 100%;
		background: var(--mq-mint);
	}
	.lesson {
		flex: none;
		width: 44px;
		min-height: 44px;
		display: grid;
		place-items: center;
		color: #fff;
		background: var(--mq-navy-deep);
		border: 3px solid var(--mq-line);
		border-radius: var(--mq-radius);
		cursor: pointer;
	}
	.card:disabled,
	.lesson:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}
	.locked {
		font-size: 1rem;
		color: var(--mq-line);
		padding: 0.15rem 0.25rem;
	}
</style>
