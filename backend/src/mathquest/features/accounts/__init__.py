"""Accounts slice: signup, login, recovery and device tokens."""

from mathquest.features.accounts.nicknames import nickname_allowed, suggest_nickname
from mathquest.features.accounts.schema import LoginResult, PlayerOut, SignupResult
from mathquest.features.accounts.service import (
    login,
    player_for_token,
    recover,
    seed_signup_word,
    signup,
)

__all__ = [
    "LoginResult",
    "PlayerOut",
    "SignupResult",
    "login",
    "nickname_allowed",
    "player_for_token",
    "recover",
    "seed_signup_word",
    "signup",
    "suggest_nickname",
]
