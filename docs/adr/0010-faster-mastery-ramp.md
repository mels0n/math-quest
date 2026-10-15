# 0010. Ramp difficulty faster and keep a skill for a short run

- Status: accepted
- Date: 2026-10-15

## Context
[ADR-0008](0008-mastery-model-tuning.md) made mastery reachable, but the ramp was
still too slow for strong players. A child answering every problem correctly and
quickly first saw a skill's top tier on the 8th problem of that skill and mastered it
on the 12th. Across the whole skill graph, with the scheduler rotating to the
lowest-rated skill after every problem, the first skill (adding within 10) was
mastered only at about the 22nd problem overall. A strong child spends many problems
on content that is too easy for them, and progress inside one skill is hard to see
because the next problem is usually a different skill.

There is no placement test yet, so every child starts each skill near its middle
tier. The model has to find a strong child's level from answers alone, quickly,
without letting a child who is only sometimes right master a skill by luck.

## Decision
We change the constants and two rules in `engine/mastery.py` and `engine/scheduler.py`.
The update rule keeps its shape: after each scored problem the rating moves by
`k * (score - predicted)`.

- **Streak bonus.** The step size is
  `k = max(0.3, 1 / sqrt(1 + attempts)) * (1 + min(streak, 2))`, where `streak` is the
  number of correct answers in a row just before this one. A run of correct answers
  moves the rating up to three times as fast. The bonus applies to a miss too, so a
  miss after a streak also takes a large step down.
- **Rating cap.** After every update the rating is capped at the top tier's
  difficulty plus 1.5. Without the cap a long streak carries the rating so far above
  the top tier that misses there stop mattering. With it, one miss on the top tier
  moves the next problem down a tier, however long the streak before it was. This
  relies on neighbouring tiers being 1.0 apart in difficulty, which is true of every
  current skill; a skill with wider tier gaps would need the cap revisited.
- **Mastery.** A skill is mastered when it has at least 6 scored attempts, predicted
  success on the top tier of at least 0.7, and at least 5 correct top-tier answers
  among the last 6. A wrong answer never turns a skill from learning to mastered.
- **Short runs.** The scheduler keeps the newest ready skill until it has had 3
  problems in a row, then picks the lowest-rated ready skill as before. A review
  (every fifth problem) inside a run neither counts toward it nor ends it.

The next problem still comes from the tier whose predicted success is closest to
0.775, and the review intervals are unchanged.

With these values, a child who answers every problem correctly reaches the top tier
on the 4th problem of a skill and masters it on the 8th. Across the whole graph,
with runs of three alternating between the ready skills, adding within 10 is mastered
at the 17th problem overall instead of about the 22nd. We measured how often a child
whose accuracy does not depend on the tier masters a skill within 60 problems of it,
over 4000 simulated runs per row:

| Correct answers | Runs that master within 60 problems |
| --------------- | ----------------------------------- |
| 60%             | 2.4%                                |
| 65%             | 5.9%                                |
| 70%             | 14.0%                               |
| 75%             | 30.5%                               |
| 80%             | 57.5%                               |
| 85%             | 84.8%                               |
| 90%             | 97.9%                               |

The tests pin the shape of this table with margins: at most 5%, 10% and 20% at 60%,
65% and 70% correct, and at least 90% at 90% correct.

## Alternatives rejected
- **Placement only.** A short placement quiz would start strong children higher, but
  it does not help a child who improves during play, and it adds a screen before the
  first problem. The model has to ramp quickly on its own either way; a placement
  quiz can still be added later on top of this.
- **Larger tier gaps.** Spreading the tiers further apart would make each step up a
  bigger jump. It makes the top tier harder for everyone and the middle tier less
  useful as practice, while the rating still needs as many answers to climb.
- **A lower predicted-success threshold.** Mastering at, say, 0.6 predicted success
  would shorten the ramp, but it lets a child who is right about two times in three
  master by luck far more often. Keeping 0.7 and asking for 5 of the last 6 on the
  top tier keeps mastery tied to recent top-tier evidence.

## Consequences
Strong children reach hard problems within a few answers and see progress within a
skill, because the same skill stays on screen for three problems. Ratings are noisier:
the streak bonus makes single steps larger, so in a long simulated run the rating
averaged over the last 50 problems is within 0.4 of the child's true level across
runs and within 1.0 in every single run (within 0.8 before this change). The cap
means a rating no longer says how far above the top tier a child is, which no rule
needs. A child right about 70% of the time still masters a skill in about one run in
seven within 60 problems; that is the accepted cost of a faster ramp. The constants
remain plain module values with tests, so retuning stays a small change.
