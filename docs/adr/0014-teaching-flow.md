# 0014. Teaching flow: lessons first, a hint ladder, feedback on mistakes, and stepping back

- Status: accepted
- Date: 2026-10-15

## Context
[ADR-0012](0012-content-packs.md) and [ADR-0013](0013-content-lint-and-review.md) give
every skill a lesson, three hints, three or four explanations and feedback for the
mistakes its generator can recognise. This record decides how play uses them: when a
lesson is shown, how practice inside a lesson is kept out of the learner's record, what
a hint costs, what a wrong answer says, how explanations are chosen, when a learner
counts as stuck, and when the game steps back to easier work.

Each of these has numbers that are judgement calls, and two structural questions: the
teaching code lives in its own feature slice, which must not import the play slice (nor
the other way round), yet both act on the same issued problems.

## Decision
**Lesson first, once.** Before the first problem of a skill that has a lesson, `next`
returns `{type: "lesson"}` instead of a problem, until the player marks the lesson seen
(`lessons_seen`, one row per player and skill; marking twice changes nothing). A skill
the player has already practiced (any scored problem) never gets one, so a player who
learned a skill before its lesson existed is not sent back to the start. A lesson can be
replayed from any problem of its skill at any time.

`next` offers the lesson only to a client that says it can show one, with the header
`X-MathQuest-Client: 2`. A page loaded before lessons shipped does not send it and keeps
getting problems instead of a response it cannot draw. The header check is removed one
release after lessons ship, once no such page can still be open.

**Examples never give a problem away.** A lesson can be replayed while a problem is on
screen, so every fixed example in a lesson or an explanation uses numbers the skill never
asks (sums past 10 in Add to 10, starts above 10 in Subtract from 10). The content lint
fails any fixed example equal to a problem the skill's generator can produce.

**The try-it costs nothing.** A lesson ends with a real generated problem at the
lesson's tier, checked by the same checker. It is stored in its own table,
`lesson_tries`, not as a flagged row in `problem_instances`. Mastery, the solved count,
the scheduler's session history and the stuck log all read `problem_instances`; a
separate table cannot leak into any of them, where a `practice_only` flag would have to
be remembered in every one of those queries, today and in every future one. A wrong
answer on the try-it gets the same mistake feedback as play. Asking for the try-it again
(a replayed lesson) returns the open one instead of starting another.

**A hint ladder with a price.** `POST /api/play/problems/{id}/hint` returns the next of
the skill's three levels (a nudge, the next step, the whole method worked on this
problem's numbers), rendered from the problem's own values. The count is kept on the
problem (`hints_used`) under the same row lock the answer route takes. A fourth request
is a 409 (`no_more_hints`) and changes nothing; a hint on a scored problem is a 409
(`problem_scored`), on a closed one `problem_closed`. The client treats the first two as
nothing to do. A correct answer is credited as if it took `min(3, wrong tries before it
+ hint levels viewed + explanations viewed)` hints, so the score is
`max(0.25, 1 - 0.25 * help)`: every wrong try, hint and explanation costs a quarter, and
a solve after the worked example still counts as a hinted solve worth a quarter.

Only the third level may state the answer. The content lint renders the first two
levels, every piece of mistake feedback and every explanation with its picture for many
problems, and fails any number in them (text, math or picture parameter, on either side
of an equals sign) equal to that problem's answer, unless the prompt shows that number
itself (as in `7 - 0`). It says when the number comes from a fixed example.

**Feedback on a wrong answer.** An incorrect answer returns `feedback`. If the checker
matched a known mistake, it is that mistake's feedback from the skill's content, with
the problem's numbers (`misconception`). Otherwise, while the problem is open, a short
generic line: `hint` when a hint is left ("Not quite. Try a hint."), else `retry`. A
problem just scored wrong with no matched mistake gets none, because its answer is
revealed. Feedback never states the answer; the lint checks it like hints. Feedback
shows right under the prompt, above the answer field, in place of the client's generic
verdict line, so it is on screen without scrolling on a small phone. The generic
feedback lines live in one table in the engine next to the rule that picks them; the
verdict lines ("That's right!") stay in the client's copy table.

**Help only where the content fits.** Hints, explanations and feedback are written over
the generator's values. A bank item or a word problem that computes its own answer has
a different answer, so those problems offer none of them (`hint_levels: 0`,
`has_explanations: false`).

**Explain it another way, in a rotation.** `POST .../explain` returns one of the
skill's approaches. The order is a rotation per player: it starts at a place drawn from
a hash of the player and skill, so different players meet a different approach first,
and moves on by one with every explanation that player has seen for that skill, across
problems and sessions. It is available only after the learner has missed the problem at
least once (a 409 `explain_after_a_try` before that), because it is for a learner who
is stuck. Each one costs credit like a hint level and is recorded with its session.
Explanation pictures show where to start and how to move (a number line's start and
jumps), never the landing point or the total: the learner still counts.

**Stuck log, without identity.** A problem scored wrong after every approach of its
skill was shown in the same session records a stuck event: skill, generator, tier, seed
and the wrong answers. Only a problem that shows the generator's numbers records one, so
(generator, tier, seed) always rebuilds the problem the learner saw. The admin export
(`GET /api/admin/stuck-log`, JSON or `?format=csv`, optional `since`, at most `limit`
events, 5000 by default and 20000 at most, oldest first) contains exactly those five
fields, the shape
`content-report --stuck` reads, and nothing about who was stuck or when. The row keeps
the player id for the warm-up rule below and so that deleting a player deletes it; that
column is never exported. In CSV the wrong answers are one cell holding a JSON list, so
commas survive and no cell can start with a spreadsheet formula character.

**Warm-up on repeated struggle.** In a session, a skill with 2 stuck events or 5
problems scored wrong (counted since its last warm-up) gets 2 problems of its weakest
prerequisite (lowest rating among its prerequisites, first listed on a tie), then play
returns to the skill if it is still ready or due for review (otherwise the scheduler
chooses as usual). A skill with no prerequisites gets no warm-up. A due review on its
slot (every fifth problem) comes before a warm-up in progress; the warm-up carries on
after it. The count restarts after each warm-up, so a learner who keeps struggling gets
another one after 5 more misses, not on every problem. Warm-up problems are ordinary
problems, stored with `warmup_for` naming the skill they serve, and count for the
prerequisite's mastery.

**Frustration guard.** After 3 problems in a row of one skill scored wrong in the
session, that skill's next problem is one tier lower than the tier the rating picks
(never below tier 0). Problems of other skills in between, and unanswered ones, do not
break the run; a correct answer ends it.

Both rules are pure functions in `engine/scheduler.py` over the session's history,
which play reads from the database and passes in: the latest 50 problems, enough for a
run, the reviews inside it, a warm-up and the misses that trigger one. Review slots
always come from the session's true problem count, not the length of that window.

**Slices stay apart.** The teaching slice serves lessons, try-its, hints, explanations
and the stuck log; the play slice issues and scores problems. They share no code: what
both need is either pure logic in the engine (regenerating a problem from what is
stored, whether a problem shows the generator's values, the feedback rule, the stuck
condition, the scheduler rules) or data in entity tables (`hints_used`,
`explanation_views`, `stuck_events`). The hint and explain routes sit under
`/api/play/problems/...` because they act on play problems; the API layer maps them to
the teaching slice.

## Alternatives rejected
- **Show every lesson, even for skills already practiced.** Interrupts a learner who
  is already competent with material they have used for weeks.
- **Try-it as a `practice_only` problem instance.** One table and one answer route, but
  every reader of `problem_instances` (solved count, mastery, history, stuck log) would
  have to filter it, and forgetting once corrupts a learner's record.
- **Explanations free, or available before any try.** A learner could read every way of
  solving the problem first and be credited with a clean solve.
- **Hints free, or only wrong tries cost.** A learner could read the worked example
  every time and be credited with a clean solve; mastery would then claim more than the
  learner can do alone.
- **Count the larger of hints and wrong tries instead of the sum.** A learner who misses
  twice and then reads two hints would pay for two steps of help instead of four.
- **A fourth hint request that repeats level 3.** Harmless, but it hides client bugs and
  makes "hints viewed" ambiguous; the client never needs it because the button goes away.
- **Explanations in a fixed order.** Every learner would meet the same approach first,
  and the first approach would do most of the teaching while the others are rarely read.
- **Random explanation order per request.** The same approach could come twice in a
  row, and "all shown in this session" would take many more requests to reach.
- **Export the stuck log with player names or times.** It is for improving content, so
  identity adds nothing and only risk; times would let a reader match events to a child
  who played at a known moment.
- **A warm-up after every miss streak, or drop to the prerequisite for good.** Too
  disruptive; a short warm-up followed by a return keeps the target skill in view.
- **Drop more than one tier, or several problems at the lower tier.** One tier is
  enough to turn a run of misses into a likely success; the rating then moves the tier
  back up on its own.
- **Teaching imports play's problem helpers (or play imports teaching).** Breaks slice
  independence and makes either slice impossible to change without the other.

## Consequences
New learners see a short lesson before each skill and can practice without penalty.
Help is always available but never free, so mastery still reflects independent work;
a learner who leans on hints masters a skill more slowly. Wrong answers say something
useful when the mistake is known. Content authors get reports of exactly which problems
learners stayed stuck on, without any way to tell who. The scheduler gains state from
the session's history, so its tests now simulate sessions. The numbers (2 stuck or 5
misses, 2 warm-up problems, 3 misses for the guard, a quarter per hint) are module
constants with tests, so tuning them is a small change.
