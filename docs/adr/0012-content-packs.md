# 0012. Content packs: validated data, a small template language, stored variants

- Status: accepted; the three-choice minimum for a choice item is relaxed to two by [0023](0023-two-option-items-count-the-first-try.md)
- Date: 2026-10-15

## Context
Generators give unlimited numbers, but most of what a learner reads is written text:
lessons, hints, explanations, feedback on common mistakes, word problems, and banked
items for skills a generator cannot cover (conceptual multiple choice, estimation).
That text is written in volume, by people and by batch tooling, and reviewed in pull
requests. It has to be checked by machine before it reaches a child: a typo in a field
name, a hint that quotes the wrong sum, or a word problem whose numbers do not match
its answer are all easy to write and hard to spot by reading.

Text also needs numbers from the problem in front of the learner ("Start at 8 and count
on 5"), and sometimes numbers computed from them. Content must never become a way to
run code, and the project already refuses to hand any string to SymPy's `sympify`
([ADR-0002](0002-own-latex-parser.md)).

[ADR-0011](0011-structured-prompts.md) stores each problem's variant and template with
its seed. This record decides how variants are chosen and what they may change.

## Decision
**Packs are data, validated on load.** A pack is a directory of YAML files:

```
content/packs/<pack>/
  pack.yaml            id, title, version (semver), complete_regions
  skills.yaml          skills, each naming its generator, tiers, grade band, keypad,
                       word_problems_fit / word_share, banked / bank_share
  world.yaml           regions in map order
  lessons/<skill>.yaml  hints/<skill>.yaml  explanations/<skill>.yaml
  word_problems/<skill>.yaml  bank/<skill>.yaml
content/slots.yaml     shared names, objects, typed units (length, time, money) and
                       contexts for word problems
```

Every file is parsed by a frozen pydantic model that rejects unknown fields. The loader
then checks the files against each other: regions exist, prerequisites exist and form
no cycle, every per-skill file names a known skill and is named after it, word problems
only exist for skills marked `word_problems_fit`, bank items only for `banked` skills,
and a skill with the `choice` keypad is fully banked with choice items. Every error
names the file and the path inside it (`lessons/add_within_20.yaml:
screens[1].visual.kind: ...`).

The engine's content package imports no generators. At boot the app binds the pack to
the generator registry (keyed by generator id): every skill's generator must exist, its
tier count must match the skill's tiers, misconception feedback may only name keys the
generator declares, and typed bank answers must be in the skill's answer form. Any
failure stops the app from starting.

**Teaching content is complete per region, not per skill.** A region listed in
`complete_regions` must have a lesson, hints and explanations for every skill in it,
plus word problems and bank items where the skill's flags ask for them. Other regions
may be partly written while content is produced in batches.

**One small template language for all text.** `{a}` inserts a value the generator chose
or a filled slot; `{obj}` and `{obj.one}` give an object's plural and singular;
`{{= expr }}` inserts a computed number; `\( ... \)` marks a math part. The expression
is written in the LaTeX subset the answer checker reads. Its names are replaced by
their numbers and the result is parsed and evaluated exactly by the engine's own parser
and SymPy bridge, so nothing reaches `sympify`. Integers print as digits; any other
rational prints as `\frac{p}{q}` and is only allowed inside a math part. A missing
name, a stray brace in text, a fraction in text or a non-rational result is an error.
Writing numbers in examples as `{{= 9 + 6 }}` lets the tests recompute them.

Two forms keep English grammar right whatever the numbers and nouns are: `{obj.a}` gives
the singular with its article ("an apple", "a pear"; from the noun's `article` in
`slots.yaml` when given, else from its first letter with a short list of exceptions such
as "a unicorn" and "an hour"), and `{n obj}` gives a number with a noun that agrees with
it ("1 rock", "5 rocks"). A visual's string parameters are templates too, so a number
line can start at the problem's own number (`start: "{big}"`).

**Word problems and bank items are variants of a generated problem.** A word problem
template is picked by seed; its slots are filled from `slots.yaml` with a random
generator seeded by the seed and template id, without repeating an entry of the same
kind (two name slots never get the same name). Its answer is the generator's, with the
generator's misconceptions, unless the template sets `answer_from: expression`; then the
expression over the values is the answer and the misconceptions are dropped. A bank
item is picked by seed; a choice item's choices are shuffled by seed and answered by
index, an expression item is checked like typed input.

**The variant is drawn from the seed and stored.** For each issued problem, a draw from
a random generator seeded by the problem seed picks `bank` with the skill's
`bank_share`, `word` with its `word_share`, else `bare`; a share counts only when the
skill has that content. The variant and template or item id are stored with the seed,
so regeneration needs no other state. A removed template falls back to the bare
problem; a removed bank item closes the problem (below). If a variant fails to render
when a problem is issued (a template that breaks for one seed), the failure is logged
and the bare problem is issued and stored instead. Seeds are drawn below 2^53 so the
browser holds them exactly.

**Choice answers are indexes.** The answer route takes exactly one of `latex` or
`choice`. A choice problem accepts only a choice within its shown range, and every
other problem only LaTeX; anything else is rejected with 422 and records nothing. A
choice attempt is stored in the existing `latex` column as `choice:<index>`. Only choice
problems store that form: the answer route rejects typed LaTeX starting with `choice:`,
so the column stays unambiguous without a migration. A choice item has at least three
choices, and a choice problem allows two tries instead of three, so a miss cannot be
followed by a sure guess.

**A shipped bank item is immutable.** An item carries its own answer, and an open
problem stores only its id. Changing a shipped item's prompt meaning, its choices
(including their order) or its answer means adding a new item with a new id and
removing the old one. A problem whose bank item is gone is closed when it is answered
(`problem_closed`), and the client moves on to a new problem.

## Alternatives rejected
- **A general template engine (Jinja2 or similar).** Loops, filters and attribute
  access are far more than text needs, and a template could reach object internals.
  It also has no notion of a number that must be checked.
- **Evaluate computed numbers with `sympify` or Python `eval`.** Both run arbitrary
  code from a string. The engine's own parser already reads exactly the needed
  arithmetic, with size limits.
- **Validate content only in a CI lint step.** A content lint adds coverage and style
  checks, but structural errors must also stop a broken pack from booting, whatever
  path it took to production.
- **Choose the variant at random and store nothing new.** The problem could not be
  regenerated with the same prompt for checking or review.
- **Store rendered prompt text per issued problem.** Duplicates content in the
  database, and old rows would keep text that a content fix had corrected.
- **A new column for choice answers.** Needs a migration and a second place to read
  attempts from, for a value the existing column holds unambiguously.

## Consequences
Content authors get immediate, located errors and cannot ship a pack that does not
match the generators. Hints and explanations can quote the learner's numbers and
computed results safely. Word problems and bank items mix into play without new
storage. ADR-0011 said the answer never depends on the variant; that still holds for
bare problems and word problems that use the generator's answer, while expression
templates and bank items carry their own answers, so removing one of those while a
problem is open can change that problem's answer. Every new generator must declare its
misconception keys, and every slot list must stay kid-safe and free of brand names.
