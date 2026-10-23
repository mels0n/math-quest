# 0024. Finding a missing number joins the placement spine

- Status: accepted
- Date: 2026-10-19

## Context
[ADR-0017](0017-planned-skill-graph.md) planned finding a missing number within 20
(1.OA.D.8) as the second grade 1 anchor, so that a grade 1 placement does not hinge on one
operation or one format. [ADR-0019](0019-six-anchor-placement-spine.md) put place value in
the grade 1 slot instead, because the skill was not built, and noted that a later batch
which adds an anchor should re-run the real-pack tests and record the result.

The second batch builds the skill. It is typed (the child types the number that goes in the
blank), so every anchor of the spine is still a skill with a ten percent guess rate. Placing
it between place value and two-digit addition makes the spine seven anchors, still asked in
at most fifteen questions ([ADR-0015](0015-placement.md)).

## Decision
**The skill is an anchor.** The spine is counting to 10, adding to 10, adding to 20, tens and
ones, finding a missing number, adding with carrying and adding unlike fractions. The search
is unchanged.

**The figures,** from the placement simulator with the honest per-anchor guess rates of
ADR-0019, over every level from "nothing passed" to "everything passed", 1000 seeded runs
per level (the worst level is shown, questions are the mean over levels):

| Learner | Hint | Within one anchor | Placed two or more too high | Questions |
| --- | --- | --- | --- | --- |
| reference | none | 95.0% | 2.4% | 14.1 |
| reference | own grade | 95.8% | 1.2% | 14.0 |
| steep | none | 99.0% | 1.0% | 14.0 |
| steep | own grade | 99.6% | 0.4% | 13.8 |

[ADR-0015](0015-placement.md)'s bar is met where it applies: the reference learner with a
grade hint is placed within one anchor at least 95% of the time and two or more anchors too
high at most 2% of the time. Without a hint the reference learner is at the limit of what
fifteen one-problem questions can tell apart, and its over-placement (2.4%) is a little above
the 2% target, as it was under ADR-0019. The real-pack test bars sit a little looser than
these figures for the same reason.

## Alternatives rejected
- **Leave it as an ordinary skill.** The target holds with it on the spine, and a single
  grade 1 anchor puts the whole grade on place value alone.
- **Raise the question limit.** Seven anchors do not need more than the fifteen questions
  that six did.
- **Make it a choice skill.** It is typed, and
  [ADR-0019](0019-six-anchor-placement-spine.md) showed what a button anchor costs.

## Consequences
The spine grows by one question's worth of ladder. A learner placed at the missing number
skill is marked past everything under it (adding to 20 and taking away to 20 among them).
A later batch that adds an anchor should re-run the real-pack placement tests and record
the figures, as this record does.
