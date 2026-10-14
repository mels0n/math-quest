"""Accounts slice: signup, login, recovery and device tokens."""

from mathquest.features.accounts.nicknames import (
    load_blocklist,
    load_nickname_words,
    nickname_allowed,
    suggest_nickname,
)
from mathquest.features.accounts.schema import LoginResult, PlayerOut, RecoverResult, SignupResult
from mathquest.features.accounts.service import (
    load_recovery_words,
    login,
    logout,
    player_for_token,
    recover,
    seed_signup_word,
    signup,
)

__all__ = [
    "LoginResult",
    "PlayerOut",
    "RecoverResult",
    "SignupResult",
    "load_blocklist",
    "load_nickname_words",
    "load_recovery_words",
    "login",
    "logout",
    "nickname_allowed",
    "player_for_token",
    "recover",
    "seed_signup_word",
    "signup",
    "suggest_nickname",
]
