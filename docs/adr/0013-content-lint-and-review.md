# 0013. Content lint, coverage targets and the admin preview

- Status: accepted
- Date: 2026-10-15

## Context
[ADR-0012](0012-content-packs.md) makes a pack fail to load when it is malformed or
does not match the generators. That catches structure, not quality: a word problem
whose wording needs a word the child cannot read yet, a sentence too long for a first
grader, a hint that breaks only for some numbers, two templates that read the same, an
answer the checker would refuse. Content is written in batches and reviewed in pull
requests, so these checks have to run by machine on every change, and a reviewer has
to be able to read every item as a child would see it before it ships.

Two questions are judgement calls with no single right answer: how to measure
"readable for K to 2", and how much content a skill needs before its region counts as
finished.

## Decision
- **A content lint runs in CI and blocks on errors.** It loads each pack, binds it to
  the generator registry through the same `SkillSource` the app uses, and renders every
  word template for 200 seeds at every tier, every bank item, and every hint,
  explanation and piece of mistake feedback for 50 seeds at every tier. Each rendered
  answer must be accepted by the answer checker in the skill's answer form. Lessons
  render once with no values, so their computed numbers use literals only.
- **Findings are errors or warnings.** Errors: broken graph or generator binding,
  unrenderable text, an answer the checker refuses, unknown or unused template slots,
  em dashes, en dashes and `--` in kid-facing text, sentences over 12 words in K to 2
  text, and near duplicates within one skill. Warnings: teaching content missing outside
  a complete region, a word outside the early-reader list, a template that never shows
  one of the generator's numbers, and near duplicates across skills.
- **Readability is two simple measures.** Sentence length in words (math, slots and
  computed numbers count as one word each) and a list of a little over two thousand
  common early-reader words, with plain inflections (`-s`, `-ed`, `-ing`, ...)
  accepted. A skill lists its own math words in `vocabulary` in `skills.yaml`. Only
  length is an error, because the word list can never be complete.
- **Near duplicates are found by token sets.** Text is lower-cased, digits and slot
  names are collapsed and punctuation dropped; two items whose token sets have a
  Jaccard similarity above 0.85 are flagged.
- **Coverage targets per skill:** a generator with 3 or more tiers and 2 or more
  mistakes it can name, 15 word templates where word problems fit, 30 bank items where
  the skill is banked, one lesson, three hints, three or four explanations. A coverage
  report shows them for every skill and runs in CI as a non-blocking artifact. In a
  region listed in `complete_regions`, any shortfall is a lint error.
- **Reviewers read content in the admin area.** The LAN-only admin
  ([ADR-0009](0009-lan-only-admin.md)) gains a read-only content view: the live pack and
  version, the coverage table, and for one skill every lesson screen, hint, explanation,
  word template and bank item rendered for a chosen seed and tier, with answers. Answers
  are shown because only an admin session on the home network can reach it.
- **Markdown in content is a small subset.** Paragraphs, lists, bold and italic, parsed
  into data and rendered as text nodes. No raw HTML is ever produced.

## Alternatives rejected
- **A readability formula (Flesch-Kincaid and similar).** Built for running prose of a
  hundred words or more; on a two-sentence hint the syllable counts swing wildly and the
  score gives the writer nothing specific to fix.
- **Make unknown words errors.** Every new context word ("kayak", "pumpkin") would break
  CI until the list caught up; the warning still shows in review.
- **Check duplicates by exact text.** Swapping one name or number would hide a copy.
- **Sample a few seeds per template.** Slot clashes and fractions in text show up only
  for some values; 200 seeds per tier runs in about a second for a full skill.
- **Preview content in a separate static site.** It would need its own build and could
  drift from what the app renders; the admin view uses the running app's catalog.
- **A full Markdown renderer.** Brings raw HTML passthrough and far more syntax than
  short teaching text needs.

## Consequences
Writers get located, specific findings before review, and a reviewer reads every item
as rendered instead of reading YAML. Declaring a region complete is now a real gate.
The word list and the 12-word limit are tuning knobs that will be adjusted as content
grows; changing either changes what passes CI for every pack. Lint time grows with the
number of templates and items, roughly linearly.
