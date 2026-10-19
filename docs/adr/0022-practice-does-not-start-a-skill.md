# 0022. Trying a skill in practice does not start it

- Status: accepted
- Date: 2026-10-17

## Context
[ADR-0020](0020-readiness-for-existing-learners.md) keeps a skill the learner has started
ready, and treats a skill under what they know as implied (known, never offered). Practice
([ADR-0016](0016-practice-and-sessions.md)) lets a child choose any open skill, including
an implied one such as counting to 10 for a learner placed at grade 2. Choosing it once
creates a mastery row, and a row made the skill "started", so one practice problem would
make the adventure offer kindergarten counting to a child who only looked.

## Decision
A mastery row records whether the skill was played outside practice
(`played_in_adventure`). A row made by a practice answer has it false; the first scored
adventure answer sets it true. Readiness counts a skill as started only when the flag is
true. Practice works as before on every open skill: it records attempts, rating and
mastery, and a skill mastered in practice counts as mastered everywhere. Only the
"started" meaning changes.

The column defaults to true, so every existing row, and every row made by placement or the
adventure, counts as played. Existing learners keep exactly what they have. Migration 0011
adds the column and downgrades by dropping it.

## Alternatives rejected
- **Derive "started" from the problems table (any adventure problem for the skill).** It
  needs a join on every readiness check and reads a table that grows with play, for a fact
  one boolean states.
- **Delete the practice-only row when practice ends.** Practice progress would be lost, and
  a skill mastered in practice would stop counting.
- **Let practice start the skill.** One tap on a skill the learner has outgrown would put it
  into their adventure.

## Consequences
A practice-only skill stays implied until the learner meets it in the adventure or masters
it. If its row is later demoted without ever being played in the adventure, it is treated
as never played, like any implied skill. Rows created by older code are unchanged.
