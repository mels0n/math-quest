# 0008. Tune the mastery model for short practice sessions

- Status: accepted, superseded in part by [ADR-0010](0010-faster-mastery-ramp.md)
- Date: 2026-10-13

## Context
Each skill has a rating that rises and falls with answers and chooses how hard the
next problem is. Mastery of a skill unlocks what follows it and schedules reviews.
Children practice in short sessions, so reaching mastery must take a realistic number
of answers. The first constants needed dozens, and in some cases over a hundred,
consecutive correct answers per skill, which no child would reach.

## Decision
`engine/mastery.py` holds an Elo-style model per skill with these values.

- Predicted success is a logistic function of rating minus problem difficulty. After
  each scored problem the rating moves by `k * (score - predicted)`.
- The step size is `k = max(0.3, 1 / sqrt(1 + attempts))`. It starts large and never
  drops below 0.3, so a skill keeps responding to the learner and is not frozen by a
  long history.
- Score is 0 for a wrong answer and otherwise 1 reduced by 0.25 per hint used (floor
  0.25). For fluency skills a slow answer is reduced further, from full credit at 3
  seconds or less down to 0.75 at 8 seconds or more.
- A skill's first rating is the difficulty of its middle tier plus 1.0, so a new
  learner starts near the content and is not buried at the bottom.
- The next problem comes from the tier whose predicted success is closest to 0.775.
- A skill is mastered when it has at least 8 attempts, predicted success on the top
  tier of at least 0.7, and at least 5 correct top-tier answers among the last 6.
- Review intervals step through 1, 3, 7 and 21 days and double after that; a missed
  review returns to 1 day.

## Alternatives rejected
- **The original constants.** They kept the rating too slow to rise, so the
  predicted-success threshold for mastery sat out of reach: dozens to over a hundred
  consecutive correct answers per skill. Raising the starting rating and flooring
  the step size fixed this without loosening the evidence required.
- **Pure accuracy counting.** A fixed count of correct answers ignores problem
  difficulty, so easy problems would earn mastery and hard ones would be punished.
  It also gives no way to pick the next tier.

## Consequences
Mastery needs a minimum of 8 attempts and a recent run of top-tier successes, so it
is reachable within a few short sessions while still requiring real evidence. The
same constants adapt downward when answers go wrong. The numbers are plain module
constants with tests, so retuning is a small change; any further change should keep
the mastery rule requiring recent top-tier evidence.
