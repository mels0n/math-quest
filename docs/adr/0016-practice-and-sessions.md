# 0016. Practice mode, twelve-problem sessions and the session summary

- Status: accepted
- Date: 2026-10-15

## Context
Until now an adventure never ended: the play screen issued problems for as long as the
page stayed open, and the only choice a player had was "next". Two things were missing.
A child (or the grown-up next to them) wants a natural stopping point and a sense of what
the time achieved. And a child who knows exactly what they want to work on, because a
skill felt shaky or a test is coming, had no way to choose it: the scheduler
([ADR-0014](0014-teaching-flow.md)) always decides.

Both changes touch the play loop that lessons, hints, warm-ups, reviews and placement
([ADR-0015](0015-placement.md)) already depend on, so they must not change what an
adventure problem is, and pages loaded before this release must keep working.

## Decision
**Adventure sessions last twelve problems.** `SESSION_PROBLEMS = 12` in the scheduler.
The review slot stays every fifth problem (`REVIEW_EVERY = 5`), so with reviews due two
of the twelve are reviews, close to one in five. Once twelve problems were issued, the
next `next` ends the session: it closes any open problem, sets `ended_at` and returns
`{type: "summary", ...}` instead of a problem. A lesson shown before a new skill does
not count toward the twelve.

**The summary** is computed on the server from the session's own rows:
skills practised (skills with a scored problem, in the order first met), skills newly
mastered (see below), problems solved, problems scored, accuracy (solved over scored,
null when nothing was scored), and the time from the first problem issued to the last
answer received. The time is measured by the server so a sleeping tablet or a changed
clock cannot distort it. `POST /api/play/sessions/{id}/end` ends a session early and
returns the same summary; calling it again on an ended session returns the summary again
rather than an error, so a retried tap is harmless. `next` on an ended session is a 409
`session_ended`, and answering a problem it closed is the existing `problem_closed`.

**Newly mastered** means scoring a problem moved its skill from learning to mastered.
The problem row records it (`newly_mastered`), and the summary lists such skills that are
still mastered when the session ends. A provisional skill confirmed by its first review
is not listed: the child knew it before the session, and placement already said so.

**Old clients stay safe.** The summary uses the client opt-in header that lessons use:
`next` returns a summary only to a client sending `X-MathQuest-Client: 3` or later. An
older page never sees an ended session and keeps getting problems as before. The check
can go one release after summaries ship, together with the lesson check.

**Practice mode.** `POST /api/play/sessions {mode: "practice", skill_id}` or
`{mode: "practice", weak_spots: true}` (exactly one of the two) starts a practice
session. The session stores its skills (`focus`).

- A chosen skill must be ready, learning, provisional or mastered (including due for
  review); a locked one is a 409 `skill_locked`. Practising ahead of the map would skip
  the prerequisites the warm-up rule relies on.
- "My weak spots" is the three learning skills with the lowest progress (predicted
  top-tier success, which is comparable across skills where raw ratings are not)
  followed by every due review. With none of either it is a 409 `no_weak_spots`; the
  picker greys the button out in that case and says why.
- `scheduler.plan_practice` chooses inside the focus: runs of three problems on a skill,
  then the lowest-rated other focus skill. There are no review slots: reviews are only
  in practice when the player asked for weak spots. Lessons, hints, explanations,
  warm-ups on a weaker prerequisite and the frustration guard work exactly as in an
  adventure, because they are what make practice useful.
- Practice is untimed. A fluency skill's speed factor is dropped from the score, so a
  child who slows down to think is never penalised for it. Mastery otherwise updates
  normally, which also means a practice session can confirm or revert a provisional skill.
- Practice has no set length and no automatic summary. "I'm done" ends it with the
  summary; the same button ends an adventure early. It appears once the problem on
  screen is scored, so it never moves the card while a child is answering.
- Practicing a skill that was already mastered (not provisional) when the session
  started records a `revisit_events` row (player, session, skill, time), at most one
  per session and skill. The session stores which of its skills were mastered at the
  start, so a skill mastered or confirmed during the session is not a revisit. Later
  features reward returning to old skills: bond stars must count distinct days
  with a revisit, not raw rows, so several short sessions on one afternoon count once.

**The skill list.** `GET /api/skills` returns every skill with the player's state
(locked, ready, learning, provisional, mastered, review due), progress, region and
whether it has a lesson, grouped in map order with empty regions left out. The practice
page shows it as a picker, each state with an icon and words (colour is never the only
signal), with a lesson button that opens the lesson before the first practice problem.

## Alternatives rejected
- **End adventures by time instead of by count.** Children work at very different
  speeds, and a timer creates exactly the pressure practice mode removes. A count is
  predictable and easy to explain ("twelve puzzles").
- **Show the summary only from `end`, with the client counting to twelve.** Two open
  tabs or a reload would count differently; the server owns the session, so it decides.
- **Return the summary to every client.** A page loaded before this release does not know
  the `summary` type and would break mid-session.
- **Let practice pick any skill, locked ones included.** Locked skills have unmet
  prerequisites, so problems there would be guesswork and the warm-up rule would
  immediately send the child back down.
- **Weak spots by lowest raw rating.** Ratings sit on each skill's own difficulty scale,
  so the weakest-rated skill would nearly always be the easiest one.
- **Count every practised problem as a revisit.** A ten-problem practice run would look
  like ten visits; one row per session and skill is what "came back to it" means.
- **Store summaries.** Everything in them is derivable from the session's problems and
  attempts; storing them would only add a second source of truth.

## Consequences
Every adventure now has a beginning, an end and a short report, and a child can steer
their own practice without losing the teaching help. The client header version is now 3,
and the play page must handle three `next` types. The summary needs one extra boolean per
problem and one JSON column per session; revisit events are a new small table that only
grows when mastered skills are practised. The numbers (twelve problems, three weak
spots) are module constants with tests.
