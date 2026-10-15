<script lang="ts">
	import type { Figure } from './layout';

	/** Draws a figure as inline SVG that scales to its container's width. */
	let { figure, kind }: { figure: Figure; kind: string } = $props();
</script>

<svg
	class="figure"
	data-visual={kind}
	viewBox="0 0 {figure.width} {figure.height}"
	width="100%"
	style:max-width="{Math.max(figure.width * 1.25, 160)}px"
	role="img"
	aria-label={figure.label}
	preserveAspectRatio="xMidYMid meet"
>
	{#each figure.shapes as s, i (i)}
		{#if s.t === 'rect'}
			<rect x={s.x} y={s.y} width={s.w} height={s.h} rx={s.rx ?? 0} fill={s.fill} stroke={s.stroke ?? 'none'} stroke-width="1" />
		{:else if s.t === 'circle'}
			<circle cx={s.cx} cy={s.cy} r={s.r} fill={s.fill} stroke={s.stroke ?? 'none'} stroke-width="1.5" />
		{:else if s.t === 'line'}
			<line x1={s.x1} y1={s.y1} x2={s.x2} y2={s.y2} stroke={s.stroke} stroke-width={s.width} stroke-linecap="round" />
		{:else if s.t === 'path'}
			<path d={s.d} fill="none" stroke={s.stroke} stroke-width={s.width} stroke-linecap="round" />
		{:else if s.t === 'poly'}
			<polygon points={s.points.map((p) => p.join(',')).join(' ')} fill={s.fill} />
		{:else}
			<text
				x={s.x}
				y={s.y}
				font-size={s.size}
				fill={s.fill}
				text-anchor={s.anchor}
				font-weight={s.bold ? 700 : 400}
				aria-hidden="true">{s.text}</text
			>
		{/if}
	{/each}
</svg>

<style>
	.figure {
		display: block;
		height: auto;
		margin: 0 auto;
		font-family: var(--mq-sans-font);
		overflow: hidden;
	}
</style>
