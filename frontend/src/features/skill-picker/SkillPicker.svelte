<script lang="ts">
	import type { SkillList } from '../../entities/problem';
	import { PixelButton, ProgressBar } from '../../shared/ui';
	import { PICKER_COPY, STATE_LABELS, canPractice, groupByRegion, hasWeakSpots } from './picker';

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

{#each groups as group (group.region_id)}
	<section class="region" aria-labelledby="region-{group.region_id}">
		<h2 id="region-{group.region_id}" class="mq-pixel">{group.name}</h2>
		<ul>
			{#each group.skills as skill (skill.skill_id)}
				{@const label = STATE_LABELS[skill.state]}
				<li class="skill" class:locked={!canPractice(skill)} data-testid="skill-{skill.skill_id}">
					<div class="info">
						<span class="name">{skill.name}</span>
						<span class="state state-{skill.state}">
							<span aria-hidden="true">{label.icon}</span>
							{label.text}
						</span>
						{#if skill.state === 'learning'}
							<ProgressBar value={skill.progress} label="{skill.name} progress" />
						{/if}
					</div>
					{#if canPractice(skill)}
						<div class="actions">
							<PixelButton
								variant="mint"
								label="{PICKER_COPY.practice} {skill.name}"
								{disabled}
								onclick={() => onPractice(skill.skill_id)}
							>
								{PICKER_COPY.practice}
							</PixelButton>
							{#if skill.has_lesson}
								<PixelButton
									variant="plain"
									label="{PICKER_COPY.lesson}: {skill.name}"
									{disabled}
									onclick={() => onLesson(skill.skill_id)}
								>
									{PICKER_COPY.lesson}
								</PixelButton>
							{/if}
						</div>
					{/if}
				</li>
			{/each}
		</ul>
	</section>
{/each}

<style>
	.weak {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.6rem;
		text-align: center;
	}
	.weak p {
		margin: 0;
		font-size: 1.1rem;
	}
	.region {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
		padding: 1rem;
		background: var(--mq-navy);
		border: 4px solid var(--mq-mint);
	}
	h2 {
		margin: 0;
		font-size: 0.8rem;
		line-height: 1.6;
		color: var(--mq-gold);
	}
	ul {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
		margin: 0;
		padding: 0;
		list-style: none;
	}
	.skill {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: space-between;
		gap: 0.75rem;
		padding: 0.75rem;
		background: var(--mq-card);
		color: var(--mq-ink);
		border-radius: var(--mq-radius);
	}
	.skill.locked {
		background: #d9dbe7;
		color: var(--mq-ink-soft);
	}
	.info {
		display: flex;
		flex-direction: column;
		gap: 0.3rem;
		flex: 1 1 10rem;
		min-width: 0;
	}
	.name {
		font-size: 1.15rem;
		font-weight: 700;
		overflow-wrap: anywhere;
	}
	.state {
		font-size: 1rem;
		color: var(--mq-ink-soft);
	}
	.state-mastered,
	.state-provisional {
		color: #047857;
	}
	.state-review_due {
		color: #9a3412;
	}
	.actions {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
	}
</style>
