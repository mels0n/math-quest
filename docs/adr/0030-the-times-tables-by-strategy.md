# 0030. The times tables, taught by strategy

- Status: accepted
- Date: 2026-10-25

## Context
The second half of the fourth batch builds the times tables 2 to 9 (3.OA.C.7) in four skills
of two tables each: 2 and 5, 3 and 4, 6 and 7, 8 and 9. Times 0, 1 and 10 are already a
skill ([ADR-0029](0029-equal-groups-and-the-first-multiplying.md)). Four things needed
deciding:

- A fact such as 7 times 6 has two orders and, for a child, two readings ("7 groups of 6"
  and "6 groups of 7"), so a named mistake like "one group too few" has two different wrong
  answers.
- A tier of one table has few facts. With the other number from 2 to 10, a table has nine
  different answers, which is enough for the spread rule (five different answers in every
  tier, none in more than a third of the draws), but only if 0, 1 and 10 do not crowd them.
- Learning a table is mostly recall, but a child who has only memorised it has nothing to
  fall back on when recall fails. The standard asks for fluency by strategy and properties,
  not only by memory.
- The nines have a mistake that no other table has: the two digits of the answer the wrong
  way round.

## Decision
- **Tiers.** Tier 0 is the first table of the pair, tier 1 the second and tier 2 both mixed.
  The other number runs from 2 to 10 and the fact is written either way round. Times 0 and 1
  stay in `mult_0_1_10`, and 10 only appears here as the other number. No tier asks for a
  missing factor or divides; those are the next batch.
- **Forms.** The form climbs with the tier. The first tier asks the sentence (`7 \times 6 = ?`)
  and "What is" with the sentence in it. The second adds "There are 7 groups of 6." The third
  adds "What is 7 times 6?" in words. The questions are the same two numbers underneath (`g`
  groups of `s`) as in multiplying groups, so a word template shows every number the
  generator holds.
- **Named mistakes.** All four skills reuse the groups keys from ADR-0029 (`added_instead`,
  `one_group_too_few`, `one_group_too_many`) and add `one_each_too_few` and `one_each_too_many`,
  which are the fact next to this one in the table: 7 times 6 answered as 7 times 5 or 7 times
  7. The groups keys change the answer by the second number, the new keys by the first, so a
  fact answered one group off and a neighbour fact are both named whichever way round the
  child reads it. The nines add `digits_swapped` (9 times 7 as 36), which only comes up when a
  nine is in the question. Duplicates (for 6 times 6, where both readings give the same wrong
  answer) are dropped, as elsewhere.
- **The hints teach the strategy of the table.** The generator writes each hint from the table
  in the fact and the other number: doubling for 2, 4 and 8, double and one more for 3, half of
  ten times for 5, the fives plus one or two more groups for 6 and 7, and ten groups less one
  for 9. Only the last hint names the answer, and the working in the first two never equals it.
  The lessons teach the same strategies with the `array` picture and use 11 and 12 as the other
  number, which the skills never ask. The nines also teach the pattern of their digits.
- **Stories are plain equal groups.** The word templates tell `g` groups of `s` in many
  settings and never write the times sign. Both numbers are from 2 to 10, so a plural noun is
  always right.
- **None is an anchor,** so the placement spine ([ADR-0019](0019-six-anchor-placement-spine.md))
  is unchanged. The mixed facts skill of the next batch is the anchor for this path.

## Alternatives rejected
- **One skill per table.** Eight skills, each with nine facts, would make a path too long for
  a child to feel progress and tiers too narrow to meet the spread rule when 0, 1 and 10 are
  left out.
- **Include 0 and 1 as the other number.** They are the whole of the previous skill, and a 0
  or a 1 would be a fifth to a quarter of the draws in a tier.
- **Teach recall only.** A child who forgets 8 times 7 has nothing to try. A strategy hint
  gives a way to rebuild the fact, and a fluent child never sees it.
- **A hint that names the fact next door.** It would show a number that can equal the answer
  of another fact in the same table and teach guessing.

## Consequences
The hint text lives in the generator, because it depends on the table, so changing a strategy
is a generator change with its tests. Division and the mixed facts reuse the same two numbers
and the same mistake keys. A child cannot yet count objects in a picture, as in ADR-0029; the
array is shown in the lesson and the explanations only.
