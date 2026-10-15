<script lang="ts">
	import { onMount, tick } from 'svelte';
	import { ApiError } from '../../shared/api';
	import '../../shared/ui';
	import './admin.css';
	import ContentView from './ContentView.svelte';
	import {
		NOT_ON_LAN,
		adminErrorMessage,
		adminLogin,
		adminLogout,
		adminMe,
		canDelete,
		deletePlayer,
		hidePlayer,
		isValidNickname,
		isValidPin,
		isValidSignupWord,
		listPlayers,
		renamePlayer,
		resetPin,
		resolveNotFound,
		setSignupWord,
		signupWordState,
		unhidePlayer
	} from '../../entities/admin';
	import type { AdminPlayer } from '../../entities/admin';

	const LIST_LIMIT = 100;

	type Phase = 'loading' | 'offlan' | 'login' | 'dashboard';
	type Panel = { id: string; kind: 'rename' | 'pin' | 'delete' };

	let phase = $state<Phase>('loading');
	let view = $state<'players' | 'content'>('players');
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

	let refreshSeq = 0;
	let playersHeading: HTMLElement | undefined = $state();
	let recoveryCard: HTMLElement | undefined = $state();

	/** Focus an element as soon as it is mounted. */
	function focusOnMount(node: HTMLElement) {
		node.focus();
	}

	/** Leave the dashboard when the session is gone or admin is off-LAN; true when it did. */
	function leaveIfSessionLost(err: unknown): boolean {
		if (!(err instanceof ApiError) || (err.status !== 401 && err.status !== 404)) return false;
		recovery = null;
		notice = '';
		panel = null;
		players = [];
		phase = err.status === 404 ? 'offlan' : 'login';
		return true;
	}

	async function refresh() {
		const seq = ++refreshSeq;
		listError = '';
		try {
			const list = await listPlayers({ query: query.trim() || undefined, limit: LIST_LIMIT });
			const word = (await signupWordState()).set;
			if (seq !== refreshSeq) return;
			players = list;
			wordSet = word;
		} catch (err) {
			if (seq !== refreshSeq) return;
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
		notice = '';
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
			if (err instanceof ApiError && err.status === 404) await handlePlayerNotFound(err, onFail);
			else if (!leaveIfSessionLost(err)) onFail(adminErrorMessage(err));
			return false;
		} finally {
			busy = false;
		}
	}

	/** A 404 on a player action is either off-LAN or a missing player; a session check tells which. */
	async function handlePlayerNotFound(err: ApiError, onFail: (m: string) => void) {
		let failure: unknown = null;
		try {
			await adminMe();
		} catch (probe) {
			failure = probe;
		}
		const verdict = resolveNotFound(failure);
		if (verdict === 'offlan') {
			leaveIfSessionLost(new ApiError(404, 'not_found', null));
		} else if (verdict === 'login') {
			leaveIfSessionLost(new ApiError(401, 'unauthorized', null));
		} else if (verdict === 'missing') {
			closePanel();
			await refresh();
			listError = adminErrorMessage(err);
		} else {
			onFail(adminErrorMessage(err));
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
		if (!isValidNickname(nickname)) {
			panelError = 'Use 3 to 16 letters, numbers, spaces, - or _.';
			return;
		}
		const ok = await run(
			() => renamePlayer(player.id, nickname),
			`Renamed to ${nickname}.`,
			(m) => (panelError = m)
		);
		if (ok) {
			closePanel();
			await refresh();
			await tick();
			playersHeading?.focus();
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
			await tick();
			recoveryCard?.focus();
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
			await tick();
			playersHeading?.focus();
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

			<nav class="row tabs" aria-label="Admin views">
				<button
					type="button"
					class:ghost={view !== 'players'}
					aria-current={view === 'players' ? 'page' : undefined}
					onclick={() => (view = 'players')}>Players</button
				>
				<button
					type="button"
					class:ghost={view !== 'content'}
					aria-current={view === 'content' ? 'page' : undefined}
					onclick={() => (view = 'content')}>Content</button
				>
			</nav>

			{#if notice}<p class="notice" role="status">{notice}</p>{/if}

			{#if recovery}
				<section
					class="card recovery"
					aria-label="New recovery word"
					tabindex="-1"
					bind:this={recoveryCard}
				>
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

			{#if view === 'content'}
				<ContentView onSessionLost={leaveIfSessionLost} />
			{:else}
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
					<h2 tabindex="-1" bind:this={playersHeading}>Players</h2>
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
													aria-label="{player.hidden ? 'Unhide' : 'Hide'} {player.nickname}"
													onclick={() => toggleHidden(player)}
													disabled={busy}
												>
													{player.hidden ? 'Unhide' : 'Hide'}
												</button>
												<button
													type="button"
													class="small"
													aria-label="Rename {player.nickname}"
													onclick={() => openPanel(player.id, 'rename', player.nickname)}>Rename</button
												>
												<button
													type="button"
													class="small"
													aria-label="Reset PIN for {player.nickname}"
													onclick={() => openPanel(player.id, 'pin', player.nickname)}>Reset PIN</button
												>
												<button
													type="button"
													class="small danger"
													aria-label="Delete {player.nickname}"
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
																<input
																type="text"
																bind:value={renameTo}
																maxlength="16"
																autocomplete="off"
																use:focusOnMount
															/>
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
																	use:focusOnMount
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
																<input
																type="text"
																bind:value={typedNickname}
																autocomplete="off"
																use:focusOnMount
															/>
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
						{#if players.length >= LIST_LIMIT}
							<p class="muted">Showing the first {LIST_LIMIT}. Search to narrow.</p>
						{/if}
					{/if}
				</section>
			{/if}
		{/if}
	</div>
</main>
