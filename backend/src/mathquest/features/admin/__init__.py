"""Admin slice: password check, admin sessions and player management."""

from mathquest.features.admin.schema import AdminLogin, AdminSessionOut, PinReset, PlayerAdminOut
from mathquest.features.admin.service import (
    MAX_PAGE,
    SESSION_TTL,
    delete_player,
    hash_password,
    list_players,
    login,
    logout,
    rename,
    reset_pin,
    revoke_all_sessions,
    session_for_token,
    set_hidden,
    set_signup_word,
    signup_word_is_set,
)

__all__ = [
    "MAX_PAGE",
    "SESSION_TTL",
    "AdminLogin",
    "AdminSessionOut",
    "PinReset",
    "PlayerAdminOut",
    "delete_player",
    "hash_password",
    "list_players",
    "login",
    "logout",
    "rename",
    "reset_pin",
    "revoke_all_sessions",
    "session_for_token",
    "set_hidden",
    "set_signup_word",
    "signup_word_is_set",
]
