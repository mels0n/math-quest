# 0019. The placement spine grows to six anchors, all typed

- Status: accepted; extended by [0024](0024-missing-number-joins-the-placement-spine.md) (a seventh anchor)
- Date: 2026-10-17

## Context
[ADR-0015](0015-placement.md) describes the placement search and measured it on the
four-anchor pack that existed then (adding to 10, adding to 20, adding with carrying,
adding unlike fractions): the reference learner landed within one anchor in 97.4% or more
of runs with no hint, over-placing at most 1.7%, in about 13.5 questions.

Building the first kindergarten batch put two more anchors on the spine, as the planned
graph ([ADR-0017](0017-planned-skill-graph.md)) intends: counting to 10 (kindergarten) and
a grade 1 anchor. ADR-0017 named comparing to 100 for that place. The spine is now
counting to 10, adding to 10, adding to 20, tens and ones, adding with carrying and adding
unlike fractions. The search is unchanged and still asks at most fifteen questions.

The simulated learners of ADR-0015 guessed right 10% of the time on every anchor. That is
fair for a typed answer, not for a question answered by three buttons (one in three) or
for a comparison of two numbers (a coin flip, then typing the number). The tests now give
each anchor the guess rate its answer format has.

## Decision
**The grade 1 anchor is tens and ones, not comparing to 100.** With the honest guess rates
a choice anchor on the spine costs too much: on the same spine with comparing to 100 as a
three-button anchor, the reference learner with a grade hint reached only 94.7% within one
anchor, with 3.7% placed two or more anchors too high, below the bar of ADR-0015. Tens and
ones is a built grade 1 skill with a typed answer, and a child cannot pass it without the
skills under it. Comparing to 100 stays a skill, no longer an anchor. This supersedes the
anchor list in ADR-0017 and the real-pack figures in ADR-0015, and nothing else in them.

**The figures,** over every level from "nothing passed" to "everything passed", 1000 seeded
runs per level, each anchor with its own guess rate (all typed here, so 10%):

| Learner | Hint | Within one anchor (worst level) | Placed two or more too high (worst level) | Questions |
| --- | --- | --- | --- | --- |
| reference | none | 94.7% | 2.4% | 14.0 |
| reference | own grade | 97.9% | 1.0% | 13.9 |
| steep | none | 99.2% | 0.8% | 13.8 |
| steep | own grade | 99.6% | 0.4% | 13.6 |

ADR-0015's bar (reference learner with a hint: 95% within one, at most 2% over) is met.
With four anchors the same figures were 97.4% and 1.7% with no hint and 97.7% and 0.7%
with the hint: a finer ladder asked with the same number of questions costs the no-hint
case about three points of accuracy and 0.7 points of over-placement. The real-pack test
bars are one point looser than these figures.

## Alternatives rejected
- **Keep comparing to 100 as the anchor.** It fails the bar under the honest model (above),
  and its typed form is a coin flip between two numbers.
- **Raise the question limit to keep the old no-hint accuracy.** A child would sit through
  more puzzles to place two anchors that mostly matter for the youngest players.
- **Drop the counting anchor.** Counting to 10 keeps a child who cannot add yet from
  landing on the floor ([ADR-0017](0017-planned-skill-graph.md)).
- **Make the grade question required.** It would meet the bar without a hint, but the game
  asks no age and the question is deliberately optional.

## Consequences
Without a grade hint the reference learner is a little less certain than before, and is
placed two or more anchors too high slightly more often (2.4% at worst, above the 2% aim
that ADR-0015 sets for the hinted case). The first review of each provisional skill catches
such a slip. Choice and comparison questions should stay off the spine; a later batch that
adds anchors should re-run the real-pack tests and update this record.
