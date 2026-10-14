# 0005. Submit answers in two phases

- Status: accepted
- Date: 2026-10-13

## Context
Scoring an answer needs the problem's state, the checker's verdict (up to 2 seconds,
see ADR-0004) and then writes to the attempt, the problem and the learner's skill
mastery. The same problem can be submitted twice at once, for example from two
devices, and two different problems of one skill can be scored at once. Each
outcome must be counted exactly once and mastery must not lose updates.

## Decision
`features/play/service.py` submits an answer as a read phase and a write phase around the check, with no transaction or row
lock held while the checker runs.

1. Lock the problem row, read its state and attempts, and commit. If the problem is
   already answered, or the answer repeats the previous wrong one, return the stored
   result here.
2. Run the checker with no transaction open.
3. Lock the problem again and re-read it. If another request scored it in the
   meantime, return the stored result. Otherwise record the attempt and, when the
   problem is now scored, lock the skill mastery row, apply the update and commit.

Rules that go with it:

- Locks are always taken in the same order: problem instance first, then skill
  mastery. The mastery row is created with `ON CONFLICT DO NOTHING` before it is
  locked, so concurrent first scores cannot deadlock or both insert.
- A problem allows three tries. The first three "wrong form" or "unreadable"
  verdicts are free; later ones use up a try, as does an incorrect answer. The count
  comes from one helper over the stored attempts, so the rule exists once.
- Sending the previous wrong answer verbatim returns the stored result and costs no
  try, so a double tap does not burn an attempt.
- Mastery changes once per problem: on the first correct answer or when the third
  try is used up.

## Alternatives rejected
- **One transaction across the check.** The row lock and a database connection would
  be held for up to 2 seconds per answer. A few slow answers would exhaust the
  connection pool and queue every other request behind a lock.
- **Optimistic retry loops.** Version columns and retries on conflict add a retry
  policy and still run the checker repeatedly for the same submission. Pessimistic
  locks around short steps are simpler and give a deterministic outcome.

## Consequences
The database is never held hostage by the checker, and duplicate or racing
submissions resolve to one stored result. The cost is that the problem is read
twice per submission and the code must keep the lock order and the "re-read after
the check" step intact; tests cover the concurrent cases, including a held mastery
lock.
