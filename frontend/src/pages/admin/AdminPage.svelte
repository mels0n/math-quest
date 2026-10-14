<script lang="ts">
	import { onMount } from 'svelte';
	import { ApiError } from '../../shared/api';
	import '../../shared/ui';
	import {
		NOT_ON_LAN,
		adminErrorMessage,
		adminLogin,
		adminLogout,
		adminMe,
		canDelete,
		deletePlayer,
		hidePlayer,
		isValidPin,
		isValidSignupWord,
		listPlayers,
		renamePlayer,
		resetPin,
		setSignupWord,
		signupWordState,
		unhidePlayer
	} from '../../entities/admin';
	import type { AdminPlayer } from '../../entities/admin';

	type Phase = 'loading' | 'offlan' | 'login' | 'dashboard';
	type Panel = { id: string; kind: 'rename' | 'pin' | 'delete' };

	let phase = $state<Phase>('loading');
	let password = $state('');
	let loginError = $state('');
	let busy = $state(false);

	let players = $state<AdminPlayer[]>([]);
	let query = $state('');
	let listError = $state('');
	let notice = $state('');
	let panel = $state<Panel | null>(null);
	let panelError = $state('');
	let renameTo = $state('');
	let newPin = $state('');
	let typedNickname = $state('');
	let recovery = $state<{ nickname: string; word: string } | null>(null);
	let copied = $state(false);

	let wordSet = $state<boolean | null>(null);
	let newWord = $state('');
	let wordError = $state('');

	/** Send the user to the right screen when the session is gone; true when it did. */
	function leaveIfSessionLost(err: unknown): boolean {
		if (err instanceof ApiError && err.status === 401) {
			phase = 'login';
			return true;
		}
		return false;
	}

	async function refresh() {
		listError = '';
		try {
			players = await listPlayers({ query: query.trim() || undefined, limit: 100 });
			wordSet = (await signupWordState()).set;
		} catch (err) {
			if (!leaveIfSessionLost(err)) listError = adminErrorMessage(err);
		}
	}

	onMount(async () => {
		try {
			await adminMe();
			phase = 'dashboard';
			await refresh();
		} catch (err) {
			if (err instanceof ApiError && err.status === 404) phase = 'offlan';
			else {
				phase = 'login';
				if (!(err instanceof ApiError && err.status === 401)) loginError = adminErrorMessage(err);
			}
		}
	});

	async function submitLogin(event: SubmitEvent) {
		event.preventDefault();
		if (busy || password === '') return;
		busy = true;
		loginError = '';
		try {
			await adminLogin(password);
			password = '';
			phase = 'dashboard';
			await refresh();
		} catch (err) {
			if (err instanceof ApiError && err.status === 404) phase = 'offlan';
			else loginError = adminErrorMessage(err);
		} finally {
			busy = false;
		}
	}

	async function signOut() {
		try {
			await adminLogout();
		} catch {
			// The cookie may already be gone; the sign-in screen is still correct.
		}
		players = [];
		recovery = null;
		phase = 'login';
	}

	function openPanel(id: string, kind: Panel['kind'], nickname: string) {
		panel = { id, kind };
		panelError = '';
		renameTo = nickname;
		newPin = '';
		typedNickname = '';
	}

	function closePanel() {
		panel = null;
		panelError = '';
	}

	async function run(action: () => Promise<unknown>, done: string, onFail: (m: string) => void) {
		if (busy) return false;
		busy = true;
		notice = '';
		try {
			await action();
			notice = done;
			return true;
		} catch (err) {
			if (!leaveIfSessionLost(err)) onFail(adminErrorMessage(err));
			return false;
		} finally {
			busy = false;
		}
	}

	async function toggleHidden(player: AdminPlayer) {
		const ok = await run(
			() => (player.hidden ? unhidePlayer(player.id) : hidePlayer(player.id)),
			player.hidden ? `${player.nickname} is visible again.` : `${player.nickname} is hidden.`,
			(m) => (listError = m)
		);
		if (ok) await refresh();
	}

	async function submitRename(player: AdminPlayer) {
		const nickname = renameTo.trim();
		const ok = await run(
			() => renamePlayer(player.id, nickname),
			`Renamed to ${nickname}.`,
			(m) => (panelError = m)
		);
		if (ok) {
			closePanel();
			await refresh();
		}
	}

	async function submitPin(player: AdminPlayer) {
		if (!isValidPin(newPin)) {
			panelError = 'The PIN needs exactly 4 numbers.';
			return;
		}
		let word = '';
		const ok = await run(
			async () => {
				word = (await resetPin(player.id, newPin)).recovery_word;
			},
			`PIN reset for ${player.nickname}.`,
			(m) => (panelError = m)
		);
		if (ok) {
			recovery = { nickname: player.nickname, word };
			copied = false;
			closePanel();
		}
	}

	async function submitDelete(player: AdminPlayer) {
		if (!canDelete(player.nickname, typedNickname)) return;
		const ok = await run(
			() => deletePlayer(player.id),
			`${player.nickname} was deleted.`,
			(m) => (panelError = m)
		);
		if (ok) {
			closePanel();
			await refresh();
		}
	}

	async function copyWord() {
		if (!recovery) return;
		try {
			await navigator.clipboard.writeText(recovery.word);
			copied = true;
		} catch {
			copied = false;
		}
	}

	async function submitWord(event: SubmitEvent) {
		event.preventDefault();
		if (!isValidSignupWord(newWord)) {
			wordError = 'Use 3 to 32 letters, with no spaces or numbers.';
			return;
		}
		wordError = '';
		const ok = await run(() => setSignupWord(newWord), 'Signup word saved.', (m) => (wordError = m));
		if (ok) {
			newWord = '';
			wordSet = true;
		}
	}

	function formatDate(value: string | null): string {
		if (!value) return 'Never';
		const date = new Date(value);
		return Number.isNaN(date.getTime()) ? 'Unknown' : date.toLocaleDateString();
	}
</script>

<svelte:head>
	<title>Math Quest admin</title>
	<meta name="robots" content="noindex" />
</svelte:head>

<main class="admin">
<div class="inner">
	{#if phase === 'loading'}
		<p>Loading...</p>
	{:else if phase === 'offlan'}
		<h1>Admin</h1>
		<p>{NOT_ON_LAN}</p>
	{:else if phase === 'login'}
		<h1>Admin sign in</h1>
		<form class="card stack" onsubmit={submitLogin}>
			<label>
				Password
				<input type="password" autocomplete="current-password" bind:value={password} />
			</label>
			{#if loginError}<p class="error" role="alert">{loginError}</p>{/if}
			<button type="submit" disabled={busy || password === ''}>Sign in</button>
		</form>
	{:else}
		<header class="bar">
			<h1>Math Quest admin</h1>
			<button type="button" class="ghost" onclick={signOut}>Sign out</button>
		</header>

		{#if notice}<p class="notice" role="status">{notice}</p>{/if}

		{#if recovery}
			<section class="card recovery" aria-label="New recovery word">
				<p>
					New recovery word for <strong>{recovery.nickname}</strong>. It is shown only once.
				</p>
				<p class="word">{recovery.word}</p>
				<div class="row">
					<button type="button" onclick={copyWord}>{copied ? 'Copied' : 'Copy'}</button>
					<button type="button" class="ghost" onclick={() => (recovery = null)}>
						I've noted it
					</button>
				</div>
			</section>
		{/if}

		<section class="card stack" aria-label="Signup word">
			<h2>Signup word</h2>
			<p class="muted">
				{wordSet === null ? '' : wordSet ? 'A signup word is set.' : 'No signup word is set yet.'}
			</p>
			<form class="row" onsubmit={submitWord}>
				<label class="grow">
					New word
					<input type="text" autocomplete="off" bind:value={newWord} maxlength="32" />
				</label>
				<button type="submit" disabled={busy || newWord === ''}>Save</button>
			</form>
			{#if wordError}<p class="error" role="alert">{wordError}</p>{/if}
		</section>

		<section class="card stack" aria-label="Players">
			<h2>Players</h2>
			<form
				class="row"
				onsubmit={(e) => {
					e.preventDefault();
					void refresh();
				}}
			>
				<label class="grow">
					Search by nickname
					<input type="search" bind:value={query} maxlength="64" />
				</label>
				<button type="submit">Search</button>
			</form>
			{#if listError}<p class="error" role="alert">{listError}</p>{/if}

			{#if players.length === 0}
				<p class="muted">No players found.</p>
			{:else}
				<div class="scroll">
					<table>
						<thead>
							<tr>
								<th>Nickname</th>
								<th>Joined</th>
								<th>Last seen</th>
								<th>Actions</th>
							</tr>
						</thead>
						<tbody>
							{#each players as player (player.id)}
								<tr class:hidden-row={player.hidden}>
									<td data-label="Nickname">
										{player.nickname}
										{#if player.hidden}<span class="tag">hidden</span>{/if}
									</td>
									<td data-label="Joined">{formatDate(player.created_at)}</td>
									<td data-label="Last seen">{formatDate(player.last_seen)}</td>
									<td class="actions">
										<button
											type="button"
											class="small"
											onclick={() => toggleHidden(player)}
											disabled={busy}
										>
											{player.hidden ? 'Unhide' : 'Hide'}
										</button>
										<button
											type="button"
											class="small"
											onclick={() => openPanel(player.id, 'rename', player.nickname)}>Rename</button
										>
										<button
											type="button"
											class="small"
											onclick={() => openPanel(player.id, 'pin', player.nickname)}>Reset PIN</button
										>
										<button
											type="button"
											class="small danger"
											onclick={() => openPanel(player.id, 'delete', player.nickname)}>Delete</button
										>
									</td>
								</tr>
								{#if panel?.id === player.id}
									<tr class="panel-row">
										<td colspan="4">
											{#if panel.kind === 'rename'}
												<form
													class="row"
													onsubmit={(e) => {
														e.preventDefault();
														void submitRename(player);
													}}
												>
													<label class="grow">
														New nickname for {player.nickname}
														<input type="text" bind:value={renameTo} maxlength="16" autocomplete="off" />
													</label>
													<button type="submit" disabled={busy || renameTo.trim() === ''}>Rename</button>
													<button type="button" class="ghost" onclick={closePanel}>Cancel</button>
												</form>
											{:else if panel.kind === 'pin'}
												<form
													class="row"
													onsubmit={(e) => {
														e.preventDefault();
														void submitPin(player);
													}}
												>
													<label class="grow">
														New 4-digit PIN for {player.nickname}
														<input
															type="text"
															inputmode="numeric"
															pattern="[0-9]*"
															maxlength="4"
															autocomplete="off"
															bind:value={newPin}
														/>
													</label>
													<button type="submit" disabled={busy || !isValidPin(newPin)}>Reset PIN</button>
													<button type="button" class="ghost" onclick={closePanel}>Cancel</button>
												</form>
											{:else}
												<form
													class="row"
													onsubmit={(e) => {
														e.preventDefault();
														void submitDelete(player);
													}}
												>
													<label class="grow">
														This cannot be undone. Type <strong>{player.nickname}</strong> to confirm.
														<input type="text" bind:value={typedNickname} autocomplete="off" />
													</label>
													<button
														type="submit"
														class="danger"
														disabled={busy || !canDelete(player.nickname, typedNickname)}
													>
														Delete
													</button>
													<button type="button" class="ghost" onclick={closePanel}>Cancel</button>
												</form>
											{/if}
											{#if panelError}<p class="error" role="alert">{panelError}</p>{/if}
										</td>
									</tr>
								{/if}
							{/each}
						</tbody>
					</table>
				</div>
			{/if}
		</section>
	{/if}
</div>
</main>

<style>
	.inner {
		max-width: 56rem;
		margin: 0 auto;
	}
	.admin {
		padding: 1rem;
		color: var(--mq-ink);
		font-family: var(--mq-sans-font);
		font-size: 1rem;
		min-height: 100vh;
		background: #f3f4f8;
	}
	.admin h1,
	.admin h2 {
		font-family: var(--mq-sans-font);
		font-weight: 700;
		letter-spacing: 0;
		margin: 0;
	}
	h1 {
		font-size: 1.5rem;
	}
	h2 {
		font-size: 1.125rem;
	}
	.bar,
	.row {
		display: flex;
		gap: 0.75rem;
		align-items: flex-end;
		flex-wrap: wrap;
	}
	.bar {
		justify-content: space-between;
		align-items: center;
		margin-bottom: 1rem;
	}
	.grow {
		flex: 1 1 12rem;
	}
	.card {
		background: var(--mq-card);
		border: 1px solid var(--mq-line);
		border-radius: var(--mq-radius);
		padding: 1rem;
		margin-bottom: 1rem;
	}
	.stack {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}
	label {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
		font-weight: 600;
	}
	input {
		font: inherit;
		padding: 0.5rem 0.625rem;
		border: 1px solid var(--mq-ink-soft);
		border-radius: var(--mq-radius);
		min-height: 2.5rem;
	}
	button {
		font: inherit;
		font-weight: 600;
		min-height: 2.5rem;
		padding: 0.4rem 1rem;
		border: 1px solid var(--mq-navy);
		background: var(--mq-navy);
		color: #fff;
		border-radius: var(--mq-radius);
		cursor: pointer;
	}
	button.ghost {
		background: transparent;
		color: var(--mq-navy);
	}
	button.danger {
		background: #b0123a;
		border-color: #b0123a;
		color: #fff;
	}
	button.small {
		min-height: 2.25rem;
		padding: 0.25rem 0.625rem;
	}
	button:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}
	button:focus-visible,
	input:focus-visible {
		outline: 3px solid var(--mq-navy);
		outline-offset: 2px;
	}
	.error {
		color: #b0123a;
		margin: 0;
	}
	.notice {
		background: #dff7ee;
		border: 1px solid var(--mq-mint);
		padding: 0.5rem 0.75rem;
		border-radius: var(--mq-radius);
	}
	.muted {
		color: var(--mq-ink-soft);
		margin: 0;
	}
	.recovery .word {
		font-size: 1.5rem;
		font-weight: 700;
		letter-spacing: 0.05em;
		margin: 0.5rem 0;
	}
	.scroll {
		overflow-x: auto;
	}
	table {
		width: 100%;
		border-collapse: collapse;
	}
	th,
	td {
		text-align: left;
		padding: 0.5rem;
		border-bottom: 1px solid var(--mq-line);
		vertical-align: middle;
	}
	.actions {
		display: flex;
		gap: 0.375rem;
		flex-wrap: wrap;
	}
	.hidden-row td:first-child {
		color: var(--mq-ink-soft);
	}
	.tag {
		font-size: 0.75rem;
		background: var(--mq-line);
		padding: 0.1rem 0.4rem;
		border-radius: var(--mq-radius);
		margin-left: 0.25rem;
	}
	.panel-row td {
		background: #f7f7fb;
	}
	@media (max-width: 40rem) {
		thead {
			display: none;
		}
		tr,
		td {
			display: block;
		}
		td[data-label]::before {
			content: attr(data-label) ': ';
			font-weight: 600;
		}
	}
</style>
