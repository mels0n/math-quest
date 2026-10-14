"""Accounts slice: signup, login, recovery and device tokens."""

from mathquest.features.accounts.nicknames import (
    load_blocklist,
    load_nickname_words,
    nickname_allowed,
    suggest_nickname,
)
from mathquest.features.accounts.schema import LoginResult, PlayerOut, RecoverResult, SignupResult
from mathquest.features.accounts.service import (
    check_nickname_available,
    load_recovery_words,
    login,
    logout,
    player_for_token,
    recover,
    replace_credentials,
    seed_signup_word,
    set_signup_word,
    signup,
    signup_word_is_set,
)

__all__ = [
    "LoginResult",
    "PlayerOut",
    "RecoverResult",
    "SignupResult",
    "check_nickname_available",
    "load_blocklist",
    "load_nickname_words",
    "load_recovery_words",
    "login",
    "logout",
    "nickname_allowed",
    "player_for_token",
    "recover",
    "replace_credentials",
    "seed_signup_word",
    "set_signup_word",
    "signup",
    "signup_word_is_set",
    "suggest_nickname",
]
