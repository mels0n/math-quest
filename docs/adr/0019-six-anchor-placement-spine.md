# 0019. The placement spine grows to six anchors

- Status: accepted
- Date: 2026-10-17

## Context
[ADR-0015](0015-placement.md) describes the placement search and measured it on the
four-anchor pack that existed then (adding to 10, adding to 20, adding with carrying,
adding unlike fractions): the reference learner landed within one anchor in 97.4% or more
of runs with no hint, over-placing at most 1.7%, in about 13.5 questions.

Building the first kindergarten batch put two more anchors on the spine, as the planned
graph ([ADR-0017](0017-planned-skill-graph.md)) intends: counting to 10 (kindergarten) and
comparing to 100 (grade 1). The spine is now counting to 10, adding to 10, adding to 20,
comparing to 100, adding with carrying and adding unlike fractions. Comparing to 100 is
answered with choices, so it is the one choice anchor. The search is unchanged and still
asks at most fifteen questions.

## Decision
Keep the search as it is and record the new figures. On the real six-anchor pack, over
every level from "nothing passed" to "everything passed", 1000 seeded runs per level:

| Learner | Hint | Within one anchor (worst level) | Placed two or more too high (worst level) | Questions |
| --- | --- | --- | --- | --- |
| reference | none | 94.7% | 2.4% | 14.0 |
| reference | own grade | 97.9% | 1.0% | 13.9 |
| steep | none | 99.2% | 0.8% | 13.7 |
| steep | own grade | 99.6% | 0.4% | 13.6 |

ADR-0015's bar (reference learner with a hint: 95% within one, at most 2% over) is met.
With four anchors the same figures were 97.4% and 1.7% with no hint and 97.7% and 0.7%
with the hint. A finer ladder asked with the same number of questions costs the no-hint
case about three points of accuracy and 0.7 points of over-placement. The real-pack test
bars are set from these figures: no hint, at least 94% within one and at most 3% over;
with the hint, 95% and 2%.

## Alternatives rejected
- **Raise the question limit to keep the old no-hint accuracy.** A child would sit
  through more puzzles to place two anchors that mostly matter for the youngest players.
- **Drop one of the new anchors.** Counting to 10 keeps a child who cannot add yet from
  landing on the floor, and comparing to 100 puts a second grade 1 anchor on the spine so
  placement does not hinge on addition alone. Both reasons are in ADR-0017.
- **Make the grade question required.** It would meet the bar without a hint, but the
  game asks no age and the question is deliberately optional.

## Consequences
Without a grade hint the reference learner is a little less certain than before, and is
placed two or more anchors too high slightly more often (2.4% at worst, above the 2% aim
that ADR-0015 sets for the hinted case). The first review of each provisional skill
catches such a slip. Each further anchor will cost a little more, so a later batch that
adds anchors should re-run the real-pack tests and update this record.
