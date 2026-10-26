# 0028. Adding with carrying to 1000 stays off the placement spine

- Status: accepted
- Date: 2026-10-25

## Context
[ADR-0017](0017-planned-skill-graph.md) planned adding three-digit numbers with carrying
(2.NBT.B.7, 3.NBT.A.2) as an anchor, the first grade 3 one. The fourth batch builds it,
together with adding and subtracting three-digit numbers without regrouping and subtracting
with borrowing. [ADR-0024](0024-missing-number-joins-the-placement-spine.md) and
[ADR-0026](0026-subtraction-with-borrowing-joins-the-placement-spine.md) both asked that a
batch which adds an anchor re-run the real-pack placement tests and record the result.

The skill is typed, so it has the ten percent guess rate of every other anchor. It builds on
adding three-digit numbers without carrying and on two-digit adding with carrying, the anchor
whose method it extends by a place.

## Decision
**The skill is not an anchor.** The spine stays at eight anchors: counting to 10, adding to
10, adding to 20, tens and ones, finding a missing number, adding with carrying, subtracting
with borrowing and adding unlike fractions. The search is unchanged and asks at most fifteen
questions ([ADR-0015](0015-placement.md)). A child placed at borrowing or at unlike fractions
is still marked past everything under it.

**The figures,** from the placement simulator with the honest per-anchor guess rates of
ADR-0019, over every level from "nothing passed" to "everything passed", 1000 seeded runs
per level (the worst level is shown, questions are the mean over levels). "Eight anchors" is
the spine of ADR-0026, which these runs reproduce exactly; "nine anchors" adds the new skill
between borrowing and unlike fractions, where the file order puts it.

| Learner | Hint | Eight anchors: within one, over, questions | Nine anchors: within one, over, questions |
| --- | --- | --- | --- |
| reference | none | 93.3%, 2.5%, 14.3 | 93.1%, 2.7%, 14.4 |
| reference | own grade | 95.5%, 1.1%, 14.1 | 94.2%, 1.2%, 14.3 |
| steep | none | 98.6%, 1.4%, 14.1 | 98.7%, 1.3%, 14.2 |
| steep | own grade | 99.4%, 0.6%, 13.9 | 99.0%, 1.0%, 14.1 |

With nine anchors the reference learner who names their grade is placed within one anchor
94.2% of the time, below the 95% that [ADR-0015](0015-placement.md) asks for, and the
no-hint rows get slightly worse. Grade 3 hints would also start at the new anchor instead of
at borrowing. That is the row that matters most, since nearly every child names a grade, so
the extra anchor costs more than it tells us. With the skill left off the spine every row
keeps the figures ADR-0026 recorded and the real-pack bars in
`tests/engine/test_placement.py` are unchanged.

## Alternatives rejected
- **Make it the ninth anchor, as planned.** It fails the bar above for the reference learner
  with a hint. Fifteen one-problem questions cannot tell nine anchors apart as well as eight.
- **Raise the question limit to pay for the extra anchor.** Every child would sit through a
  longer round for one more rung that mostly matters to older children, and the target is
  met for children who name their grade without it.
- **Swap it for subtracting with borrowing.** Replacing that anchor with this one measures
  better without a hint (94.6% within one, 1.6% over) and the same with the hint (95.5%,
  1.1%). It would leave grade 2 resting on adding alone, which is what ADR-0026 added the
  borrowing anchor to prevent, and it would take back a decision made one batch ago on the
  strength of a single figure. If grade 2 and 3 placement matter more later, this is the
  measured option to revisit.

## Consequences
A child placed at either two-digit anchor (adding with carrying or subtracting with
borrowing) is not marked past any of the four three-digit skills, because none of them is
below those anchors: they are the next skills in the canyon, and the first practice settles
each. A later batch that wants a grade 3 anchor should build one on a skill that is not one
rung above an existing anchor, or settle the question-limit trade above first, and should
record its figures as this record does.
