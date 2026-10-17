# 0017. A digit of a shown number counts as shown in word problems

- Status: accepted
- Date: 2026-10-17

## Context
The content lint warns when a word problem uses the generator's answer but never shows
one of the generator's numbers, because the learner could not work the problem out. A
number counts as shown when the template writes it, or when it always equals a number
the template writes (`big` and `small` always equal one of the two addends).

The two-digit addition skills give their hints the tens and ones of each addend
(`a_tens`, `a_ones`, `b_tens`, `b_ones`), and place value gives the answer digit. A
word problem about `{a}` and `{b}` shows the whole numbers, so the learner sees every
digit, but the rule did not know that and warned on every template of both skills.

## Decision
A value also counts as shown when, for every sampled problem, it equals one digit of a
number the template shows. The check is exact and runs over the same samples as before,
so a value that matches only by chance in some problems is still reported. The rule's
message and level are unchanged.

## Alternatives rejected
- **Keep the digits out of the generator's values and compute them in text.** The
  template language has no floor or remainder, and adding them for this one check would
  widen what content can do for little gain.
- **Mark such values as hint-only in the generator.** A second list of names per
  generator to keep in step with its builder, for something the lint can see directly.
- **Accept the warnings.** A warning on every template hides the one that matters.

## Consequences
Hint and explanation writers can use place-value digits freely without touching word
problems. A word template that shows only one of two numbers is still reported, because
the other number's digits are not digits of the one shown.
