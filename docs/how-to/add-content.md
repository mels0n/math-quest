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

Files live in `content/packs/<pack>/`, one file per skill and kind:
`lessons/<skill>.yaml`, `hints/<skill>.yaml`, `explanations/<skill>.yaml`,
`word_problems/<skill>.yaml`, `bank/<skill>.yaml`. The schemas are in
[`mathquest/engine/content/schema.py`](../../backend/src/mathquest/engine/content/schema.py),
and the design (template language, variants, complete regions) is in
[ADR-0012](../adr/0012-content-packs.md). Copy an existing file for the shape;
`add_within_20` has every kind except bank items.

Bump `version` in `pack.yaml` with every content change, so the admin page shows which
version is live.

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
- **No em dashes or en dashes,** and no `--`. Use a full stop or a comma instead.
- **Vary names and contexts.** Use name, object and context slots (`{name}`, `{obj}`)
  rather than writing names in, and spread templates across home, school, nature, food
  and games. Two templates that read nearly the same fail the lint.
- **Let numbers compute.** Write any number that depends on other numbers as
  `{{= a + b }}`, and numbers in worked examples as `{{= 9 + 6 }}`, so the lint
  recomputes them. Never type a sum by hand.
- **Mistake feedback names the mistake kindly and points to the fix.** Say what the
  child probably did ("It looks like you took away."), then what to do instead ("The
  plus sign means put them together."). Never say "wrong".
- **Hints climb.** The first is a nudge, the second the next step, the third the whole
  answer worked out.
