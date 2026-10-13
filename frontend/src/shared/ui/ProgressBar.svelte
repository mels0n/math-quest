<script lang="ts">
	let { value, label }: { value: number; label: string } = $props();
	const pct = $derived(Math.round(Math.min(1, Math.max(0, value)) * 100));
</script>

<div
	class="bar"
	role="progressbar"
	aria-label={label}
	aria-valuemin="0"
	aria-valuemax="100"
	aria-valuenow={pct}
>
	<div class="fill" style:width="{pct}%"></div>
</div>

<style>
	.bar {
		height: 1.1rem;
		background: var(--mq-navy-deep);
		border: 3px solid var(--mq-line);
		overflow: hidden;
	}
	.fill {
		height: 100%;
		background: repeating-linear-gradient(90deg, var(--mq-mint) 0 10px, #05b385 10px 12px);
		transition: width 0.4s steps(8);
	}
</style>
