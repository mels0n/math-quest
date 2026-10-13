export interface Player {
	id: string;
	nickname: string;
}

export interface PlayerEnvelope {
	player: Player;
}

/** Signup and recovery both return the new recovery word, which is shown once. */
export interface PlayerWithRecovery extends PlayerEnvelope {
	recovery_word: string;
}
