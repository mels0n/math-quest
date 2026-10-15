"""Limits shared by every place a learner answers a problem (play and a lesson's try-it)."""

MAX_ATTEMPTS = 3
"""Tries on a typed problem; a miss uses one."""
MAX_CHOICE_ATTEMPTS = 2
"""Tries on a choice problem: with three or more choices a third try would be a free guess."""
STORED_LATEX_MAX = 200
"""Typed answers longer than this are unreadable and stored cut to this length."""
SEED_LIMIT = 2**53
"""New seeds are below this, so they are exact as JavaScript numbers."""
