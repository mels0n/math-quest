import { login, recover, signup } from '../../entities/player';
import type { Player, PlayerEnvelope, PlayerWithRecovery } from '../../entities/player';

export type AuthMode = 'signup' | 'login' | 'recover';

export interface AuthFields {
	nickname: string;
	pin: string;
	signupWord: string;
	recoveryWord: string;
}

export interface AuthApi {
	login: (nickname: string, pin: string) => Promise<PlayerEnvelope>;
	signup: (signupWord: string, nickname: string, pin: string) => Promise<PlayerWithRecovery>;
	recover: (nickname: string, recoveryWord: string, newPin: string) => Promise<PlayerWithRecovery>;
}

export type AuthOutcome =
	| { kind: 'signed_in'; player: Player }
	| { kind: 'reveal'; word: string; player: Player };

const defaultApi: AuthApi = { login, signup, recover };

/** Signup and recovery end on the recovery-word screen; login goes straight in. */
export async function submitAuth(
	mode: AuthMode,
	fields: AuthFields,
	api: AuthApi = defaultApi
): Promise<AuthOutcome> {
	const nickname = fields.nickname.trim();
	if (mode === 'login') {
		return { kind: 'signed_in', player: (await api.login(nickname, fields.pin)).player };
	}
	const result =
		mode === 'signup'
			? await api.signup(fields.signupWord.trim(), nickname, fields.pin)
			: await api.recover(nickname, fields.recoveryWord.trim(), fields.pin);
	return { kind: 'reveal', word: result.recovery_word, player: result.player };
}

export interface RecoveryReveal {
	/** The word to show, or null once the kid has confirmed they wrote it down. */
	word: () => string | null;
	acknowledge: () => void;
}

/** Holds the new recovery word until acknowledged; the player is signed in only then. */
export function createRecoveryReveal(
	outcome: { word: string; player: Player },
	onSignedIn: (player: Player) => void
): RecoveryReveal {
	let word: string | null = outcome.word;
	return {
		word: () => word,
		acknowledge() {
			if (word === null) return;
			word = null;
			onSignedIn(outcome.player);
		}
	};
}
