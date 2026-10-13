<script lang="ts">
	import { onMount } from 'svelte';
	import type { MathfieldElement } from 'mathlive';
	import type { KeypadProfile } from '../../entities/problem';
	import { keysFor, type Key } from './keypad';

	let {
		profile,
		disabled = false,
		onSubmit
	}: {
		profile: KeypadProfile;
		disabled?: boolean;
		onSubmit: (latex: string) => void;
	} = $props();

	let host: HTMLDivElement;
	let field = $state.raw<MathfieldElement | null>(null);
	const keys = $derived(keysFor(profile));

	export function clear() {
		if (field) field.value = '';
		field?.focus();
	}

	export function focus() {
		field?.focus();
	}

	function submit() {
		const latex = field?.value.trim() ?? '';
		if (latex !== '' && !disabled) onSubmit(latex);
	}

	function press(key: Key) {
		if (!field || disabled) return;
		const { action } = key;
		if (action.kind === 'go') submit();
		else if (action.kind === 'insert') field.insert(action.latex);
		else field.executeCommand(action.command);
		if (action.kind !== 'go') field.focus();
	}

	onMount(() => {
		let gone = false;
		void import('mathlive').then(({ MathfieldElement: Field }) => {
			if (gone) return;
			Field.fontsDirectory = null;
			Field.soundsDirectory = null;
			const mf = new Field();
			host.append(mf);
			mf.mathVirtualKeyboardPolicy = 'manual';
			mf.menuItems = [];
			mf.setAttribute('inputmode', 'none');
			mf.setAttribute('aria-label', 'Your answer');
			mf.setAttribute('data-testid', 'math-field');
			mf.addEventListener('keydown', (event) => {
				if (event.key === 'Enter') {
					event.preventDefault();
					submit();
				}
			});
			field = mf;
			mf.focus();
		});
		return () => {
			gone = true;
			field?.remove();
			field = null;
		};
	});

	$effect(() => {
		if (field) field.readOnly = disabled;
	});
</script>

<div class="answer">
	<div class="field" bind:this={host}></div>
	<div class="pad" role="group" aria-label="Answer keypad" data-profile={profile}>
		{#each keys as key (key.name)}
			<button
				type="button"
				class="key {key.tone ?? ''}" class:del={key.name === 'Delete'}
				aria-label={key.name}
				{disabled}
				onpointerdown={(e) => e.preventDefault()}
				onclick={() => press(key)}>{key.label}</button
			>
		{/each}
	</div>
</div>

<style>
	.answer {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}
	.field :global(math-field) {
		display: block;
		width: 100%;
		min-height: 4rem;
		font-size: 2rem;
		padding: 0.25rem 0.75rem;
		color: var(--mq-ink);
		background: #fff;
		border: 3px solid var(--mq-ink-soft);
		border-radius: var(--mq-radius);
		--caret-color: var(--mq-berry);
		--selection-background-color: #ffe9a8;
	}
	.field :global(math-field:focus-within) {
		outline: none;
		border-color: var(--mq-navy);
		box-shadow: var(--mq-focus);
	}
	.field :global(math-field::part(virtual-keyboard-toggle)),
	.field :global(math-field::part(menu-toggle)) {
		display: none;
	}
	.pad {
		display: grid;
		grid-template-columns: repeat(5, 1fr);
		gap: 0.5rem;
	}
	.key {
		min-height: var(--mq-tap);
		font-family: var(--mq-sans-font);
		font-size: 1.5rem;
		font-weight: 700;
		color: var(--mq-ink);
		background: #eef0f7;
		border: 3px solid var(--mq-ink-soft);
		border-radius: var(--mq-radius);
		box-shadow: 0 3px 0 var(--mq-ink-soft);
		touch-action: manipulation;
		cursor: pointer;
	}
	.key.aux {
		background: #dfe3f2;
	}
	.pad[data-profile='numbers'] .key.del {
		grid-column: span 2;
	}
	.pad[data-profile='numbers'] .key.mint {
		grid-column: span 3;
	}
	.key.mint {
		grid-column: 1 / -1;
		background: var(--mq-mint);
		border-color: var(--mq-navy-deep);
		box-shadow: 0 3px 0 var(--mq-navy-deep);
		font-family: var(--mq-pixel-font);
		font-size: 1rem;
	}
	.key:active:not(:disabled) {
		transform: translateY(2px);
		box-shadow: 0 1px 0 var(--mq-ink-soft);
	}
	.key:focus-visible {
		outline: none;
		box-shadow: var(--mq-focus);
	}
	.key:disabled {
		opacity: 0.5;
	}
</style>
