<script lang="ts">
	import { suggestNickname } from '../../entities/player';
	import type { Player } from '../../entities/player';
	import { PixelButton } from '../../shared/ui';
	import { createRecoveryReveal, submitAuth, type AuthMode, type RecoveryReveal } from './auth-flow';
	import { authErrorMessage } from './messages';
	import PinPad from './PinPad.svelte';
	import RecoveryWord from './RecoveryWord.svelte';

	let { onSignedIn }: { onSignedIn: (player: Player) => void } = $props();

	let mode = $state<AuthMode>('login');
	let nickname = $state('');
	let signupWord = $state('');
	let recoveryWord = $state('');
	let pin = $state<string | null>(null);
	let pinKey = $state(0);
	let busy = $state(false);
	let error = $state('');
	let reveal = $state<RecoveryReveal | null>(null);
	let shownWord = $state<string | null>(null);

	async function reroll() {
		try {
			nickname = await suggestNickname();
		} catch {
			// Typing a nickname by hand still works.
		}
	}

	function choose(next: AuthMode) {
		mode = next;
		error = '';
		pin = null;
		pinKey += 1;
		if (next === 'signup' && nickname === '') void reroll();
	}

	async function submit(event: SubmitEvent) {
		event.preventDefault();
		if (busy) return;
		if (pin === null) {
			error = 'Tap your 4 PIN numbers first.';
			return;
		}
		busy = true;
		error = '';
		try {
			const outcome = await submitAuth(mode, { nickname, pin, signupWord, recoveryWord });
			if (outcome.kind === 'signed_in') {
				onSignedIn(outcome.player);
			} else {
				reveal = createRecoveryReveal(outcome, onSignedIn);
				shownWord = reveal.word();
			}
		} catch (err) {
			error = authErrorMessage(err);
			pin = null;
			pinKey += 1;
		} finally {
			busy = false;
		}
	}
</script>

{#if reveal && shownWord !== null}
	<RecoveryWord
		word={shownWord}
		onDone={() => {
			reveal?.acknowledge();
			shownWord = reveal?.word() ?? null;
		}}
	/>
{:else}
	<form class="panel" onsubmit={submit}>
		<div class="tabs">
			<button
				type="button"
				aria-pressed={mode !== 'signup'}
				class:on={mode !== 'signup'}
				onclick={() => choose('login')}>Log in</button
			>
			<button
				type="button"
				aria-pressed={mode === 'signup'}
				class:on={mode === 'signup'}
				onclick={() => choose('signup')}>New player</button
			>
		</div>

		{#if mode === 'signup'}
			<label>
				Secret word from your grown-up
				<input name="signup_word" bind:value={signupWord} autocomplete="off" required />
			</label>
		{/if}

		<div class="field">
			<label for="nickname">Nickname</label>
			<span class="row">
				<input
					id="nickname"
					name="nickname"
					bind:value={nickname}
					autocomplete="off"
					minlength="3"
					maxlength="16"
					required
				/>
				{#if mode === 'signup'}
					<PixelButton variant="plain" label="Pick another nickname" onclick={reroll}>
						&#8635;
					</PixelButton>
				{/if}
			</span>
		</div>

		{#if mode === 'recover'}
			<label>
				Recovery word
				<input name="recovery_word" bind:value={recoveryWord} autocomplete="off" required />
			</label>
		{/if}

		<div class="pin">
			<span class="label">{mode === 'recover' ? 'Choose a new PIN' : 'Your 4 number PIN'}</span>
			{#key pinKey}
				<PinPad onComplete={(value) => (pin = value)} />
			{/key}
		</div>

		{#if error}<p class="error" role="alert">{error}</p>{/if}

		<PixelButton type="submit" variant="gold" disabled={busy}>
			{mode === 'signup' ? "Let's go!" : mode === 'recover' ? 'Get back in' : 'Play'}
		</PixelButton>

		{#if mode === 'login'}
			<button type="button" class="link" onclick={() => choose('recover')}>
				Forgot your PIN?
			</button>
		{:else if mode === 'recover'}
			<button type="button" class="link" onclick={() => choose('login')}>Back to log in</button>
		{/if}
	</form>
{/if}

<style>
	.panel {
		display: flex;
		flex-direction: column;
		gap: 1rem;
		padding: 1.25rem;
		background: var(--mq-navy);
		border: 4px solid var(--mq-line);
	}
	.tabs {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 0.5rem;
	}
	.tabs button {
		min-height: var(--mq-tap);
		font-family: var(--mq-pixel-font);
		font-size: 0.7rem;
		color: #fff;
		background: var(--mq-navy-deep);
		border: 4px solid var(--mq-navy-deep);
		cursor: pointer;
	}
	.tabs button.on {
		border-color: var(--mq-gold);
		color: var(--mq-gold);
	}
	label,
	.label {
		font-weight: 600;
	}
	.field,
	label:has(input) {
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
		font-weight: 600;
	}
	.row {
		display: flex;
		gap: 0.5rem;
	}
	input {
		flex: 1;
		min-height: var(--mq-tap);
		padding: 0.5rem 0.75rem;
		font: inherit;
		font-size: 1.2rem;
		color: var(--mq-ink);
		background: var(--mq-card);
		border: 4px solid var(--mq-line);
		border-radius: var(--mq-radius);
	}
	input:focus-visible {
		outline: none;
		box-shadow: var(--mq-focus);
	}
	.pin {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.5rem;
	}
	.error {
		margin: 0;
		padding: 0.6rem 0.8rem;
		background: var(--mq-berry);
		color: #fff;
		font-weight: 600;
	}
	.link {
		min-height: var(--mq-tap);
		background: none;
		border: 0;
		color: var(--mq-mint);
		font: inherit;
		text-decoration: underline;
		cursor: pointer;
	}
</style>
