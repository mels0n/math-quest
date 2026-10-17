# Add or change content

How to write a batch of teaching content (lessons, hints, explanations, word problems,
bank items) for one or more skills, check it, and get it merged. Commands run in
`backend/` unless noted.

## 1. Pick the skills

Run the coverage report to see which skills are short of the targets:

```
uv run content-report
```

It prints a table per region: tiers, mistakes the generator can name, word templates,
bank items, lesson, hints and explanations, each as `have/want`. Add `--json` for the
same numbers as JSON.

When a stuck-problem export is available (a JSON list of
`{"skill", "generator", "tier", "seed", "wrong_answers": [...]}` objects), pass it in
to see where learners get stuck most:

```
uv run content-report --stuck stuck.json
```

Start with skills that have the most stuck problems, then regions closest to complete.

## 2. Make a branch

```
git switch -c content/<slug>
```

Use a short slug for the batch, such as `content/meadows-hints`.

## 3. Write the YAML

Before you write:

- Set `word_problems_fit: true` on the skill in `skills.yaml` before adding word
  problems; the loader rejects them otherwise.
- Mistake feedback is keyed by the mistakes the generator declares. A new mistake needs a
  generator change (with a property test) before it can have feedback.
- A lesson or explanation example must never be a problem the skill asks, whether it is
  written as math or as plain text; the lint fails it
  ([ADR-0013](../adr/0013-content-lint-and-review.md),
  [ADR-0021](../adr/0021-typed-comparing-skills-with-a-tiered-bank.md)). Write worked
  questions in words, with numbers the skill never uses.
- Digits of a number a word problem shows count as shown, so hints may use them
  ([ADR-0018](../adr/0018-digits-count-as-shown-in-word-problems.md)).

Files live in `content/packs/<pack>/`, one file per skill and kind:
`lessons/<skill>.yaml`, `hints/<skill>.yaml`, `explanations/<skill>.yaml`,
`word_problems/<skill>.yaml`, `bank/<skill>.yaml`. The schemas are in
[`mathquest/engine/content/schema.py`](../../backend/src/mathquest/engine/content/schema.py),
and the design (template language, variants, complete regions) is in
[ADR-0012](../adr/0012-content-packs.md). Copy an existing file for the shape;
`add_within_20` has every kind except bank items.

Bump `version` in `pack.yaml` with every content change, so the admin page shows which
version is live.

A bank item that has shipped is never edited in place: changing its meaning, its
choices (even their order) or its answer means adding a new item with a new `id` and
removing the old one. Open problems store only the id, so an edited item would be
checked against an answer the learner never saw. A choice item needs at least three
choices.

Template forms beyond `{a}` and `{{= expr }}`:

- `{obj.a}` writes the singular with its article: "an apple", "a pear". Give a noun an
  `article` in `slots.yaml` when its spelling misleads.
- `{n obj}` writes a number with a noun that agrees: "1 rock", "5 rocks".
- Unit slots come from typed pools: `length_units`, `time_units`, `money_units`.
- A visual's string parameters are templates: `start: "{big}"` starts a number line at
  this problem's bigger number. Each must render to a whole number.

Visuals (`visual: {kind, params}`) and their params. Unknown params and numbers out of
range are load errors; a template that goes out of range for some problem is a lint
error:

| kind | params |
| --- | --- |
| `number_line` | `min`, `max` (at most 100 apart), `start`, `jumps` (a list of jump sizes, negative goes left, or one number `n` for `n` jumps of one), `end` |
| `base_ten` | `hundreds`, `tens`, `ones` |
| `fraction_bars` | `bars`: one to four `{parts, shaded}` |
| `area_model` | `rows`, `cols` (one to three parts of each factor), `show_products` |
| `algebra_tiles` | `x2`, `x`, `units` (negative counts draw negative tiles) |
| `array` | `rows`, `cols` (1 to 12) |
| `clock` | `hour` (1 to 12), `minute` |
| `money` | `dollars`, `quarters`, `dimes`, `nickels`, `pennies` |

A region listed in `complete_regions` must meet every target for every skill in it.
Add a region there only when the report shows it done.

## 4. Lint locally

```
uv run content-lint
```

Every finding prints as `level: file:path: rule: message`. Errors fail CI; fix all of
them. Read every warning: an unknown word may be fine (add it to the skill's
`vocabulary` in `skills.yaml` if the skill needs it), a near duplicate across skills
may be worth rewording. The rules and their reasons are in
[ADR-0013](../adr/0013-content-lint-and-review.md).

The lint does not know what a story means. Whether a story's action matches the skill
(a "gives away" story on an adding skill) is for you and the reviewer to check in the
preview.

## 5. Read every item in the preview

Start the app locally with an admin password, sign in at `/admin` and open
**Content**. Click a skill to see every lesson screen, hint, explanation, word template
and bank item rendered, with answers. Change the seed and tier, or press **Resample**,
and read a few samples of each template. Check that the numbers make sense in the story
and that the answer shown is the one the text asks for.

## 6. Open a pull request

Push the branch and open a pull request. CI runs the lint and attaches the coverage
report as a build artifact. The maintainer reads the new items in the preview page
before merging.

## Style guide for writers

- **Short sentences for K to 2.** At most 12 words per sentence (math and names count as
  one word each). One idea per sentence. Prefer common words; the lint lists any word
  outside the early-reader list.
- **Warm and direct.** Talk to the child as "you". Encourage effort, never speed.
- **No em dashes or en dashes,** no `--` and no spaced hyphen (" - ") as a dash. Use a
  full stop or a comma instead.
- **Vary names and contexts.** Use name, object and context slots (`{name}`, `{obj}`)
  rather than writing names in, and spread templates across home, school, nature, food
  and games. Two templates that read nearly the same fail the lint, even with one noun
  or verb swapped. Use `{obj.a}` and `{n obj}` so articles and plurals stay right.
- **Let numbers compute.** Write any number that depends on other numbers as
  `{{= a + b }}`, and numbers in worked examples as `{{= 9 + 6 }}`, so the lint
  recomputes them. Never type a sum by hand.
- **Mistake feedback names the mistake kindly and points to the fix.** Say what the
  child probably did ("It looks like you took away."), then what to do instead ("The
  plus sign means put them together."). Never say "wrong", and never give the answer:
  the child still has to find it. The lint fails feedback that writes the answer as the
  result of an equation.
- **Ask a clear question.** Say whose things are counted ("How many shells does Mia
  have?", not "How many shells?"), keep numbers realistic for the story, and do not
  start a sentence with a number ("There are 6 birds", not "6 birds").
- **Hints climb.** The first is a nudge, the second the next step, the third the whole
  answer worked out. Only the third may state the answer; the lint checks the first two.
- **Explanations are different ways in.** Each approach (visual, steps, story, worked)
  should make sense on its own: a child who asks again gets the next one, and a child
  who has seen them all and still misses is logged as stuck for review.

## Build a batch of planned skills

Skills that are designed but have no generator yet live in
`content/packs/<pack>/planned_skills.yaml` ([ADR-0017](../adr/0017-planned-skill-graph.md)).
The file is never loaded for play; `content-lint` checks it together with the built
skills, and `content-report` ends with the planned skills per region and per batch. The
fields and rules are described in the header of the file. Batch numbers are permanent:
when a batch is built its entries leave the file, and the plan starts at its lowest
remaining batch. To build the next batch, take that number from the report and:

1. Write and register a generator for each skill, with the tier count the plan gives
   (see [ADR-0012](../adr/0012-content-packs.md)).
   Let tiers span the skill's whole range and get harder through the form of the question
   (before, a missing number, counting on, a sum, a question in words), not by narrowing the
   numbers: every tier needs at least five different answers, and no answer a third of the
   draws (`test_every_batch_one_tier_has_a_spread_of_answers`). `add_within_10` and the
   other skills built before batch 1 still narrow their tiers by total; revisiting them is a
   follow-up.
2. Move each entry from `planned_skills.yaml` to `skills.yaml`: add `generator`, drop
   `batch` and `unlocks`, and keep `standards`. Put it in `skills.yaml` where it sits in
   the plan, ahead of the first skill of any later region, because the file order breaks
   ties in the topological order and so decides the placement spine.
   A typed skill can serve a bank of button questions: set `banked: true`, a
   `bank_share` such as 0.3 and a `tier` on each item
   ([ADR-0021](../adr/0021-typed-comparing-skills-with-a-tiered-bank.md)). A `choice`
   keypad skill is answered by buttons alone and needs `bank_share: 1` and its bank in the
   same change; prefer a typed skill with a bank. Bank items need at least 30 different
   wordings, not different numbers. Counting objects needs a picture that is not built yet,
   so a groups skill tells counts as numerals.
3. Apply each promoted skill's `unlocks`: for every built skill it named, add the new
   skill's id to that skill's `prerequisites` in `skills.yaml`.
   When it names a skill that is still planned, add the promoted id to that planned
   entry's `prerequisites` in `planned_skills.yaml` instead.
4. Delete the moved entries from `planned_skills.yaml`. A skill left in both files is a
   lint error. If a later batch needs a different shape (a skill split, merged or
   moved), change the plan in the same pull request.
5. Write the teaching content for the new skills (the steps above), and bump `version`
   in `pack.yaml`. A change that touches only `planned_skills.yaml` changes nothing a
   learner sees and needs no bump.
6. Update what the batch changes around the pack: `EARLY_SKILLS` in `backend/tests/conftest.py`
   (the skills a test player has passed, so tests about older skills keep their ready set;
   leave out a skill that builds on one the tests use), the practice picker height bound in
   `frontend/e2e/session.spec.ts` (measure it, then set it about 15% above), the placement
   test bars if the spine changed ([ADR-0019](../adr/0019-six-anchor-placement-spine.md)),
   and the longest-prompts fixture (`UPDATE_FIXTURES=1 uv run pytest
   tests/engine/test_prompt_fixture.py`). A batch that adds prerequisites under skills
   learners have played is covered by [ADR-0020](../adr/0020-readiness-for-existing-learners.md).
