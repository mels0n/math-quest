<script lang="ts">
	import { onMount } from 'svelte';
	import type { MathfieldElement } from 'mathlive';
	import type { KeypadProfile } from '../../entities/problem';
	import { noticeAfterEdit, submitBlocker } from './guard';
	import { layoutFor, type Key } from './keypad';

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
	const layout = $derived(layoutFor(profile));
	let ready = $state(false);
	let notice = $state('');

	export function clear() {
		if (field) field.value = '';
		notice = '';
		field?.focus();
	}

	export function focus() {
		field?.focus();
	}

	function submit() {
		const latex = field?.value.trim() ?? '';
		if (latex === '' || disabled) return;
		const blocker = submitBlocker(latex);
		if (blocker !== null) {
			notice = blocker;
			return;
		}
		notice = '';
		onSubmit(latex);
	}

	function press(key: Key, event: MouseEvent) {
		if (!field || disabled) return;
		notice = noticeAfterEdit();
		const { action } = key;
		if (action.kind === 'go') submit();
		else if (action.kind === 'insert') field.insert(action.latex);
		else field.executeCommand(action.command);
		// Pointer taps keep the caret in the field; keyboard presses keep focus on the key.
		if (action.kind !== 'go' && event.detail > 0) field.focus();
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
			// Physical-keyboard spaces are dropped in math mode; keep them so "1 5/12" stays a mixed number.
			mf.mathModeSpace = '\\,';
			mf.setAttribute('inputmode', 'none');
			mf.setAttribute('aria-label', 'Your answer');
			mf.setAttribute('data-testid', 'math-field');
			mf.addEventListener('input', () => {
				notice = noticeAfterEdit();
			});
			mf.addEventListener('keydown', (event) => {
				if (event.key === 'Enter') {
					event.preventDefault();
					submit();
				}
			});
			field = mf;
			ready = true;
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
	<p class="notice" role="status" data-testid="answer-notice">{notice}</p>
	<div class="pad" role="group" aria-label="Answer keypad" data-profile={profile}>
		<div class="block digits">
			{#each layout.digits as key (key.name)}
				{@render keyButton(key)}
			{/each}
		</div>
		{#if layout.extras.length > 0}
			<div class="block extras">
				{#each layout.extras as key (key.name)}
					{@render keyButton(key)}
				{/each}
			</div>
		{/if}
		<div class="go">{@render keyButton(layout.go)}</div>
</div>
</div>

{#snippet keyButton(key: Key)}
	<button
		type="button"
		class="key {key.tone ?? ''}"
		class:zero={key.name === '0'}
		aria-label={key.name}
		disabled={disabled || !ready}
		onpointerdown={(e) => e.preventDefault()}
		onclick={(e) => press(key, e)}>{key.label}</button
	>
{/snippet}

<style>
	.answer {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}
	.notice {
		margin: 0;
		min-height: 1.5rem;
		font-weight: 700;
		color: var(--mq-berry);
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
		grid-template-columns: auto 1fr;
		gap: 0.5rem;
		align-items: start;
	}
	.pad[data-profile='numbers'] {
		grid-template-columns: 1fr;
	}
	.block {
		display: grid;
		grid-template-columns: repeat(3, minmax(var(--mq-tap), 1fr));
		gap: 0.5rem;
	}
	.pad:not([data-profile='numbers']) .digits {
		width: min(20rem, 55vw);
	}
	.pad[data-profile='numbers'] .digits {
		max-width: 22rem;
		margin: 0 auto;
		width: 100%;
	}
	.go {
		grid-column: 1 / -1;
	}
	@media (max-width: 34rem) {
		.pad:not([data-profile='numbers']) {
			grid-template-columns: 1fr;
		}
		.pad:not([data-profile='numbers']) .digits {
			width: 100%;
		}
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
	.key.zero {
		grid-column: span 2;
	}
	.key.mint {
		width: 100%;
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
