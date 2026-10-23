# 0026. Subtracting with borrowing joins the placement spine

- Status: accepted
- Date: 2026-10-23

## Context
[ADR-0017](0017-planned-skill-graph.md) planned adding and subtracting two-digit numbers
with regrouping (grade 2) as anchors. Only adding with carrying was built so far. Subtracting
with borrowing (2.NBT.B.5) is the second grade 2 anchor, so that a grade 2 placement does not
hinge on one operation. [ADR-0024](0024-missing-number-joins-the-placement-spine.md)
made the spine seven anchors and noted that a later batch which adds an anchor should
re-run the real-pack tests and record the result.

The third batch builds the skill. It is typed (the child types the number left), so every
anchor of the spine is still a skill with a ten percent guess rate. It needs only
subtracting two-digit numbers without borrowing, which needs taking away within 20 and
taking away tens, so it sits after adding with carrying and before unlike fractions.

## Decision
**The skill is an anchor.** The spine is counting to 10, adding to 10, adding to 20, tens
and ones, finding a missing number, adding with carrying, subtracting with borrowing and
adding unlike fractions. The search is unchanged and still asks at most fifteen questions
([ADR-0015](0015-placement.md)).

**The first question changes for a child with no grade hint.** With no hint, placement
starts at the middle of the anchors in grades K to 2. That was adding to 20 with seven
anchors, six of them in those grades. Eight anchors put seven of them in those grades, so
the middle is now tens and ones. A grade hint is unaffected, except that grade 3 now starts
at borrowing, the last grade 2 anchor, where it started at carrying.

**The figures,** from the placement simulator with the honest per-anchor guess rates of
ADR-0019, over every level from "nothing passed" to "everything passed", 1000 seeded runs
per level (the worst level is shown, questions are the mean over levels). The real-pack
test in `tests/engine/test_placement.py` runs this simulation and holds the bars below.

| Learner | Hint | Within one anchor | Placed two or more too high | Questions |
| --- | --- | --- | --- | --- |
| reference | none | 93.3% | 2.5% | 14.3 |
| reference | own grade | 95.5% | 1.1% | 14.1 |
| steep | none | 98.6% | 1.4% | 14.1 |
| steep | own grade | 99.4% | 0.6% | 13.9 |

With seven anchors the same four rows measured 95.0%, 95.8%, 99.0% and 99.6% within one
anchor ([ADR-0024](0024-missing-number-joins-the-placement-spine.md)).

[ADR-0015](0015-placement.md)'s bar is met where it applies: the reference learner with a
grade hint is placed within one anchor at least 95% of the time and two or more anchors too
high at most 2% of the time. Without a hint the reference learner is below 95% within one
anchor (93.3%) and a little above the 2% target for over-placement (2.5%). That learner was
already at the limit of what fifteen one-problem questions can tell apart on seven anchors;
the eighth anchor spends the same budget over a longer ladder. The real-pack bar for that
row is set one point looser than the measurement (92.3% and 3.5%); the other three rows keep
the bars they had, which they still meet.

## Alternatives rejected
- **Leave it as an ordinary skill.** The target holds with it on the spine, and the grade 2
  anchor would rest on adding alone.
- **Raise the question limit.** It would win back the no-hint row, but every child pays for
  it with a longer round, and the target is met for children who name their grade, which is
  nearly all of them.
- **Make it a choice skill.** It is typed, and
  [ADR-0019](0019-six-anchor-placement-spine.md) showed what a button anchor costs.

## Consequences
The spine grows by one question's worth of ladder. A learner placed at borrowing is marked
past everything under it (adding with carrying among them). A later batch that adds an
anchor should re-run the real-pack placement tests and record the figures, as this record
does, and should weigh again whether fifteen questions are enough for the no-hint row.
