export interface Player {
	id: string;
	nickname: string;
}

export interface PlayerEnvelope {
	player: Player;
}

/** GET /api/me: the signed-in player and their saved count of solved problems. */
export interface MeEnvelope extends PlayerEnvelope {
	total_solved: number;
}

/** Signup and recovery both return the new recovery word, which is shown once. */
export interface PlayerWithRecovery extends PlayerEnvelope {
	recovery_word: string;
}
