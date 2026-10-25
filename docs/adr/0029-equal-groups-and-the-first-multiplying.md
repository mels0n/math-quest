# 0029. Equal groups, arrays and the first multiplying

- Status: accepted
- Date: 2026-10-25

## Context
The fourth batch builds the start of the multiplication path in Operation Canyon: equal
groups (2.OA.C.4), rows and columns (2.OA.C.4), multiplying groups (3.OA.A.1, 3.OA.A.3) and
the zero, one and ten facts (3.OA.C.7, 3.OA.B.5). The times tables and division build on
them, so the choices here set the pattern for those skills.

Four things in the plan did not fit what the app can show or score:

- A question cannot carry a picture, and counting drawn objects is the gap that
  [ADR-0021](0021-typed-comparing-skills-with-a-tiered-bank.md) and
  [ADR-0027](0027-time-and-graphs-in-words-and-typed-bank-skills.md) left open for clocks and
  graphs. Groups and arrays are pictures too.
- Grade 2 finds a total by adding the group again and again or by skip counting. The times
  sign is a grade 3 idea.
- The plan's array tiers ("up to 3 by 3", "up to 4 by 4", "up to 5 by 5") have too few
  answers at the bottom: a 2 or 3 by 2 or 3 array totals 4, 6 or 9, and the spread rule asks
  for five different answers in every tier and no answer in more than a third of the draws.
- Times 0 would answer 0 in half the draws of a tier made of times 1 and times 0.

## Decision
- **Groups and arrays are told in words and numerals,** as clocks and graphs are: "There are
  4 bags. Each bag has 3 apples." and "Chairs are in 3 rows of 5." The lessons and the
  explanations carry the picture, with the `array` visual (rows of dots, one row per group)
  and, for skip counting, a number line.
- **The times sign starts at multiplying groups.** Equal groups and arrays never write it,
  in a question, a hint or a lesson, and a test pins that. Multiplying groups writes "3 groups
  of 4" and `3 \times 4` side by side, in a story, as "There are 3 groups of 4" and as the
  sentence, so the sign is always tied to the words it stands for. The checker's LaTeX parser
  already reads `\times`. The sentence form appears from the second tier.
- **Tiers.**
  - Equal groups keeps the plan's size ladder, which holds the spread rule (groups of 2 with 2
    to 9 groups, groups of 3, 4 or 5, then mixed sizes with 10). The top tier also gives the
    repeated addition as a sum in about a third of its draws.
  - Rows and columns moves to a form ladder: "rows of", "rows and columns", then an array that
    gains or loses a row. Every array stays within 5 by 5, the standard's limit, and every
    tier has at least eight different answers.
  - Multiplying groups keeps the plan's ladder by number of groups (two, up to five, up to
    ten).
  - Zero, one and ten keeps the plan's kinds (1 and 0, 10, mixed). Times 0 is drawn in a
    quarter of the first tier and a fifth of the mixed tier, so that no one answer is a third
    of the draws. Both orders come up in every tier ("3 times 0" and "0 times 3"), which is
    the turn-around idea of 3.OA.B.5, and the groups form ("There are 5 groups of 0") joins
    from the second tier.
  - No tier asks for a missing factor or divides; those are batch 5.
- **One set of named mistakes for groups.** Both groups skills name `added_instead` (the
  number of groups plus the size, 4 groups of 3 as 7), `one_group_too_few` and
  `one_group_too_many`. Division and the times tables should reuse these keys. Arrays name
  the same three for rows (`added_rows_and_columns`, `counted_one_row`, `one_row_short`) and,
  in the top tier, forgetting the change, changing the total by one thing and changing the
  row the wrong way. The zero, one and ten skill names the answer copied from the other
  number, adding one, answering zero for times one, and, for ten, dropping the zero, adding
  two zeros and adding ten.
- **Stories hold only the two numbers they tell.** The groups generators give `g` (groups) and
  `s` (size) and nothing else numeric, so every word template shows every number the
  generator holds and keeps the generator's answer. Names in the generator's own stories are
  picked from four, by the numbers, so a tier's questions can all be listed (the lint scans
  them to check that a lesson never shows a problem the skill asks). The word templates tell
  equal groups in five settings and always have at least two groups of at least two, so a
  plural noun is right.
- **Zero, one and ten counts every try.** Its first tier does have an answer the question
  shows (times 1 answers the other number, and times 0 answers a number it names), but its
  second tier does not and its mixed tier shows it in about half the draws, so it is not
  flagged `first_try_counts` ([ADR-0023](0023-two-option-items-count-the-first-try.md)). The
  lessons use 12 and 15, which the skill never asks.
- **None of the four is an anchor,** so the placement spine ([ADR-0019](0019-six-anchor-placement-spine.md))
  is unchanged.

## Alternatives rejected
- **Keep the plan's array tiers.** The bottom tier would have three answers.
- **Use the times sign in grade 2.** It would teach the sign before the idea it stands for,
  and the standard asks for skip counting and repeated addition.
- **Wait for a picture in the question.** It would hold back the skills for a feature the
  words can stand in for, as with clocks and graphs.
- **Make times 0 half of the first tier.** A guess of 0 would be right half the time.

## Consequences
A child cannot count objects in a drawing until a question can carry a picture; that change
could replace the text of these questions without changing tiers or answers. The times tables
and division build on the same two numbers (`g` and `s`), the same mistake keys and the same
`\times` sentence.
