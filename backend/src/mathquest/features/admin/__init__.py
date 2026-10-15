"""Admin slice: password check, admin sessions, player management and content preview."""

from mathquest.features.admin.content import SAMPLE_SEEDS, overview, skill_preview
from mathquest.features.admin.content_schema import ContentOverview, SkillPreview
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
    "SAMPLE_SEEDS",
    "SESSION_TTL",
    "AdminLogin",
    "AdminSessionOut",
    "ContentOverview",
    "PinReset",
    "PlayerAdminOut",
    "SkillPreview",
    "delete_player",
    "hash_password",
    "list_players",
    "login",
    "logout",
    "overview",
    "rename",
    "reset_pin",
    "revoke_all_sessions",
    "session_for_token",
    "set_hidden",
    "set_signup_word",
    "signup_word_is_set",
    "skill_preview",
]
