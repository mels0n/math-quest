# 0023. Two-option items count only the first try

- Status: accepted
- Date: 2026-10-19

## Context
[ADR-0021](0021-typed-comparing-skills-with-a-tiered-bank.md) made the comparing skills
count only the first try, because a question with two likely answers lets a guess be
followed by a sure right answer, and a learner who always finds the right one on a second
try would otherwise reach mastery by guessing. It applied the rule to typed problems whose
generator is flagged `first_try_counts`, and kept the plain rule for bank choice items:
[ADR-0012](0012-content-packs.md) requires at least three choices, and a choice problem
allows two tries, so a miss never leaves a sure guess.

The second batch of skills meets the same trap in two more places:

- "Is this number sentence true?" (1.OA.D.7) has exactly two answers, true and false. A
  bank item with three choices would need a made-up third one.
- A fact family question ("You know that 4 + 9 = 13. What is 13 - 4?") has an answer that
  is one of the numbers the prompt shows (tiers 0 and 1 show the whole family), so a few
  guesses reach it. Tier 2 shows only the two numbers of the sentence, so its answer is not
  on the page, but it keeps the same scoring so a child's rating does not depend on the tier.

The skill for true and false sentences was also planned as a `choice` keypad skill. A
lesson's try-it is a generated problem answered by typing
([ADR-0021](0021-typed-comparing-skills-with-a-tiered-bank.md)), so a skill answered by
buttons alone cannot have a try-it that the child can answer.

## Decision
- **A choice item may have two choices.** The minimum is two (it was three).
- **A choice problem with exactly two choices counts only the first try.** If the learner
  misses and then picks the other choice, the problem is scored as a miss: a zero in the
  rating and a miss in the recent outcomes. The two tries, the feedback and the "That's
  right" copy stay, so the child still sees what was right. A choice problem with three or
  more choices keeps the plain rule. The test is `first_try_only` in the mastery module,
  which the play service applies to the problem it regenerated, so it covers every bank
  item that has two choices and nothing else that has choices.
- **A generator whose answer is, in most of its tiers, one of the numbers its prompt shows
  is flagged `first_try_counts`.** The fact family generator is, as the comparing
  generators are.
- **Equal or Not is a typed skill with a bank.** Its generator asks the learner to make
  both sides of a sentence equal (`4 + 3 = 5 + ?`), which a lesson's try-it can ask. Its
  bank holds the true or false items, tagged by tier, with two choices each and about half
  of them true. The bank serves 40% of the draws.

## Alternatives rejected
- **Keep Equal or Not as a `choice` keypad skill with a full bank.** Its lesson could not
  have a try-it that is answerable, and its generator, hints and mistake feedback would be
  unreachable, which is what ADR-0021 removed for the comparing skills.
- **Give true or false a third choice.** "Cannot tell" is not an answer a first grader is
  taught to give, and it would make a real question harder than it is.
- **Allow one try on a two-choice item.** The child would see no feedback on a miss. The
  second try is where the feedback and the right answer are shown; only its score changes.
- **Score two-choice items by the plain rule and rely on the mastery model.** The
  simulated guesser of ADR-0021 reaches mastery on a two-way question under the plain
  rule, so the rule has to change, not the model.

## Consequences
A guesser cannot master a skill through true or false items or fact families. A child who
misses a two-choice item once is told so honestly: the miss counts even though the second
try is right. Authors may write two-choice items in any bank, and they are handled by the
same rule without a flag. The status line of ADR-0012 and ADR-0021 point here; their
decision texts are unchanged.
