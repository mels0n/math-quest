# 0021. Comparing skills are typed, with a tiered bank for what needs buttons

- Status: accepted
- Date: 2026-10-17

## Context
The first batch of kindergarten skills includes three about comparing: groups (more,
fewer, same), numbers to 20 and numbers to 100. They were first built as choice skills
([ADR-0012](0012-content-packs.md): a `choice` keypad skill is fully banked, and play only
shows its bank items). That had three costs found in review:

- A lesson's try-it is a generated problem answered by typing, so a choice skill's try-it
  showed a question with nothing to answer it with.
- The generator of a choice skill is never shown, so its tiers, its named mistakes and
  the hints and feedback written for them could not be reached.
- A bank item carries no tier, so a learner at the easiest tier met the hardest items.

## Decision
- The comparing skills have the `numpad` keypad. The generator asks the main question and
  the learner types the number: "Which number is bigger, 12 or 13?", "How many are in the
  group with more?". Tiers, mistakes, hints and feedback all apply.
- Their bank holds what needs buttons: the signs (greater than, less than, equal) for
  grade 1, and groups or numbers that are the same or equal, about one item in four, so
  that always choosing "same" is no strategy. The bank is served with `bank_share: 0.3`.
  A numpad skill may serve choice bank items: the problem carries its `choices` and the
  card draws buttons for it, as it already does for any bank problem.
- A bank item has an optional `tier`. A problem at a tier draws only from items with that
  tier or none, and the bank's share only counts when the tier has such items. Every item
  of the comparing banks is tagged.
- Only the first try counts. A comparison has two likely answers, so a wrong try is
  followed by a sure right one and guessing would master the skill. Their generators carry
  `first_try_counts`: for a bare or word problem a solve after a wrong try is scored as a
  miss (a zero in the rating and a miss in `recent`), while the tries, the feedback and the
  "That's right" copy stay. Bank choice items keep the plain rule, since they allow two
  tries and have three or more choices. A simulated guesser who always finds the right
  number on the second try reaches mastery under the plain rule and never under this one.
- The groups skill keeps numerals: counting objects is K.CC.B.5 and needs a picture of
  countable objects, a visual that does not exist yet. It is a separate follow-up; until
  then groups are told as numbers and the first batch does not claim to teach counting
  a set.
- The example lint ([ADR-0013](0013-content-lint-and-review.md)) also compares lesson and
  explanation examples with bank prompts, and with runs of numbers with a blank written in
  plain text ("7, 8, _, 10"), not only with math parts. It looks up the kind of an example
  first (its numbers blanked) among the kinds of problem the skill asks, which are few and
  found quickly; only an example that looks like one of them needs the exact scan, so a
  worked question in words no longer makes a skill with a huge problem space warn.

## Alternatives rejected
- **Keep choice skills and give the try-it choices.** The try-it would need the bank
  as well as a generator, and the unreachable generator content would stay unreachable.
- **A choice answer form for every comparison.** Typing the number is the grade level
  skill; buttons for a coin-flip question teach less and place worse
  ([ADR-0019](0019-six-anchor-placement-spine.md)).

## Consequences
The comparing skills get mistakes with feedback, hints and a tiered ramp like any typed
skill. A banked typed skill can mix bank items of its own tier into play. A bank item that
has shipped is still immutable; its tier is part of that. The picture for counting a
group is not built.
