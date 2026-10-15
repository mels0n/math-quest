<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import { fetchSkills, practiceHref, weakSpotsHref } from '../../entities/problem';
	import type { SkillList } from '../../entities/problem';
	import { PICKER_COPY, SkillPicker } from '../../features/skill-picker';
	import { ApiError, commonErrorMessage } from '../../shared/api';
	import { PixelButton, PixelFrame } from '../../shared/ui';

	let list = $state<SkillList | null>(null);
	let notice = $state<string | null>(null);

	async function load() {
		notice = null;
		try {
			list = await fetchSkills();
		} catch (err) {
			if (err instanceof ApiError && err.status === 401) {
				void goto('/');
				return;
			}
			notice = commonErrorMessage(err);
		}
	}

	onMount(() => {
		void load();
	});
</script>

<PixelFrame title="PRACTICE">
	{#snippet hud()}
		<PixelButton variant="plain" label="Settings" onclick={() => void goto('/settings')}>&#9881;</PixelButton>
	{/snippet}

	{#if notice}
		<div class="notice" role="alert">
			<p>{notice}</p>
			<PixelButton variant="gold" onclick={() => void load()}>Try again</PixelButton>
		</div>
	{/if}

	<p class="lead">{PICKER_COPY.intro}</p>
	{#if list}
		<SkillPicker
			{list}
			onPractice={(id) => void goto(practiceHref(id))}
			onLesson={(id) => void goto(practiceHref(id, true))}
			onWeakSpots={() => void goto(weakSpotsHref)}
		/>
	{:else if !notice}
		<p class="lead" role="status">Loading your skills...</p>
	{/if}
	<div class="back">
		<PixelButton variant="mint" onclick={() => void goto('/play')}>{PICKER_COPY.back}</PixelButton>
	</div>
</PixelFrame>

<style>
	.lead {
		margin: 0;
		font-size: 1.15rem;
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
	.back {
		display: flex;
		justify-content: center;
	}
</style>
