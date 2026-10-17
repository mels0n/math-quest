# 0020. New prerequisites never send an existing learner back

- Status: accepted
- Date: 2026-10-17

## Context
A skill is ready when every prerequisite is mastered ([ADR-0012](0012-content-packs.md),
`SkillGraph.ready`). Building a batch from the planned graph
([ADR-0017](0017-planned-skill-graph.md)) adds prerequisites to skills that already
exist: counting to 10 under adding and subtracting to 10, teen numbers under tens and
ones. A learner who already played those skills has never mastered the new prerequisite,
so with the plain rule the skill they were learning becomes locked, and one placed at
grade 2 before the change is offered kindergarten counting first.

Stored data cannot be edited to fix this: prerequisites only affect readiness, and a
migration that invents mastery rows would also invent review dates and ratings.

## Decision
Readiness stays a pure function of the graph and the learner's skill records, with two
additions, both in `SkillGraph`:

- **A started skill stays ready.** A skill the learner has a record of (learning,
  mastered, provisional or due for review) is offered whatever prerequisites it gained
  since. Mastered skills are still never offered.
- **A skill under what the learner knows is implied.** A skill that has dependents, none
  of which is unmet (each is mastered, provisionally mastered or itself implied), counts
  as known for the prerequisite check, whether or not it was ever played. It is not
  offered by the scheduler, but the practice picker shows it as open, so a child can still
  choose it.

The play service passes the learner's record of started skills to the scheduler and to
the skill list; no stored row changes.

## Alternatives rejected
- **A migration that marks the new prerequisites provisionally mastered for everyone who
  has started a dependent.** It writes ratings and review dates for skills nobody played,
  and cannot be undone when a later batch changes the graph again.
- **Ignore the problem until content is released.** The branch changes the graph under
  accounts that already exist, and the first symptom would be a child's current skill
  locking.
- **Imply a skill when any dependent is known.** One placed skill would then hide
  everything under it, including skills with other dependents the learner has not met.

## Consequences
A learner who knows every skill that builds on a new foundation never meets it, and one
who knows only some still does (a new player gets counting first, as intended). The
implied rule is deliberately narrow: it needs every dependent known, so a skill with no
dependents in the pack is never implied. Placement already marks every ancestor of the
frontier, so new learners are not affected.
