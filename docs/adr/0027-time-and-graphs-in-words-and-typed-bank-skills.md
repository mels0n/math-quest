# 0027. Clocks and graphs are told in words, and two planned choice skills are typed

- Status: accepted
- Date: 2026-10-23

## Context
The third batch of skills includes five that the plan left to the last pieces of grade 1
and 2: telling time to the hour and half hour (1.MD.B.3), reading a graph (1.MD.C.4), even
and odd numbers (2.OA.C.3), comparing numbers to 1000 (2.NBT.A.4) and story problems to 100
(2.OA.A.1).

Three things in the plan did not fit what the app can show or score:

- A clock face and a bar graph are pictures. The visuals module draws a clock, but a
  generator's prompt is text and math; it cannot carry a picture, and counting drawn
  objects is the same gap that [ADR-0021](0021-typed-comparing-skills-with-a-tiered-bank.md)
  left open.
- Even or odd and comparing to 1000 were planned with the `choice` keypad, answered by
  buttons alone. [ADR-0023](0023-two-option-items-count-the-first-try.md) found the problem
  with that: a lesson's try-it is a generated problem the child answers by typing, so a
  skill answered by buttons alone has a try-it with nothing to answer it with, and its
  generator, its named mistakes and the hints written for them are never reached.
- Story problems to 100 keep the shapes of [ADR-0025](0025-story-problems-compute-their-own-answers.md)
  and need the same answer-from-expression templates.

## Decision
- **A clock is told in words and numerals.** A question says where the short hand and the
  long hand point ("The short hand points to 7. The long hand points to 12."), or what a
  digital clock shows ("4:30"). The answer is always a whole number: an hour, a count of
  minutes after the hour, or a count of half hours between two times. The lesson, not the
  question, shows the clock picture. The tiers are the hour, half past, and the hour or half
  hour mixed with half hours between two clock times. No question asks for more than sixty
  minutes; longer spans are the elapsed time skill. The minutes in a half past question are
  never written as a numeral in the question, so the answer cannot be copied from it.
- **A graph is a short table of numerals.** A question lists three groups with how many
  kids chose each ("Cats: 4. Dogs: 7. Birds: 3.") and asks one question about it. The three
  counts are always different, so the biggest and the smallest group are each one group.
  The tiers read one count, compare two groups and put groups together. The numerals are
  what a bar graph's bars come to; a picture of the bars is a follow-up.
- **Even or odd and comparing to 1000 are typed skills with a bank.** The child types the
  number a question asks for (the even one of two numbers, the next odd number, the
  bigger of two numbers), as the comparing skills to 100 do. Naming a number even or odd,
  the signs and "the same" are the bank, served with `bank_share` 0.4 for even or odd and
  0.3 for comparing to 1000. Each bank has more than thirty items with different wordings,
  tagged by tier, and a wrong choice is sometimes one off and sometimes further. About one
  comparing item in four holds two equal numbers (8 of 33), so always choosing a side is no strategy.
  This changes the plan's keypad for both skills from `choice` to `numpad`.
- **Four of the five count only the first try.** Clock hours, reading a graph, even or odd
  and comparing to 1000 carry `first_try_counts`: in most of their forms the answer is one
  of two or three numbers the question shows, so a second try after a miss would be a
  sure guess ([ADR-0023](0023-two-option-items-count-the-first-try.md)). Story problems to
  100 do not; their answers are new numbers.
- **Story problems to 100 follow ADR-0025.** The generator gives an adding pair and a
  taking-away pair of two-digit numbers (at most 100), every word template computes its own
  answer and serves the tiers its shape is told in, and hints and feedback name no
  operation. Tier 0 adds to or takes from, tier 1 puts together, takes apart or compares,
  and tier 2 mixes the shapes that take apart and compare with the ones where the change or
  the start is unknown. Every number told is at least 10, so a noun after one is always plural.

## Alternatives rejected
- **Build the clock and graph pictures first.** It would hold back the skills until a
  generator can carry a visual. Told in words, the skills teach the same reading, and the
  lesson already shows a clock.
- **Keep the two `choice` skills.** They would have a try-it nobody could answer and an
  unreachable generator, the costs [ADR-0021](0021-typed-comparing-skills-with-a-tiered-bank.md)
  already measured for the comparing skills.
- **Let story problems to 100 reuse the Story Problems to 20 generator with a bigger range.**
  The two skills would then read alike. The generator for 100 draws two-digit counts, so a
  noun after a number is always plural, and its sums carry and its take-aways cross tens.

## Consequences
A child can answer every question of the five skills by typing, and the bank adds the
button questions beside them. Reading a clock from a drawing and reading a bar graph are
not tested until the visuals can ride in a question. A future change that lets a
generator's prompt carry a picture can replace the text of those two skills' questions
without changing their tiers or their answers.
