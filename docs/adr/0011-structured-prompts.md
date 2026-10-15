# 0011. Structured prompts, stored variants and skill keypads

- Status: accepted, amended in part by [ADR-0012](0012-content-packs.md)
- Date: 2026-10-15

## Context
A prompt used to be one LaTeX string, with its words wrapped in `\text{...}`. That
made words part of the math: they did not wrap on a phone, the client had to split the
string again to lay it out, a screen reader got LaTeX, and word problems (sentences
with a few numbers in them) would have been mostly `\text` groups.

Later content adds other ways to present the same generated problem: as a word
problem built from a template, or as a multiple-choice bank item. A problem is stored
as its skill, tier and seed and regenerated on demand, so whatever chooses the
presentation has to be stored too.

The keypad a learner gets was chosen by each generator in code, from three loose
names, while the skill pack is where content authors decide what a skill asks for.

## Decision
- A prompt is a list of parts. A text part holds plain words, shown as wrapping text;
  a math part holds LaTeX, set as inline math. No math part contains `\text`. The API
  sends `prompt: [{kind: "text" | "math", value}]`.
- Each generator also returns the named values it chose (`a`, `b`, `number` ...), for
  hint and word-problem templates.
- Every issued problem stores `variant` (`bare`, `word` or `bank`) and `template_id`
  with its seed. Regeneration uses them; a variant or template that no longer exists
  falls back to the bare prompt. The answer always comes from the generator and never
  depends on the variant, so checking stays correct either way.
- The keypad is a property of the skill, declared in `skills.yaml` as one of eight
  profiles: `numpad`, `numpad_neg`, `fraction`, `mixed`, `decimal`, `exponent`,
  `algebra`, `choice` (answer buttons, no keypad). An unknown profile fails loading.
- A shared file of sample key sequences per profile, `testdata/keypad-samples.json`,
  is checked from both sides: the browser test taps each sequence and compares the
  answer field's LaTeX, and the backend parses that LaTeX to the expected value.
- A decimal answer is the exact rational it spells (`3.25` is 13/4, `.5` is 1/2).
  There is no rounding tolerance: `0.333` is not 1/3.

## Alternatives rejected
- **Keep one LaTeX string and split it in the client.** This was the interim fix. It
  parses LaTeX in the browser and still sends words as math to everything else.
- **Markdown-like prompt text with inline math delimiters.** Needs escaping rules for
  every author and a parser on both sides; a list of parts needs neither.
- **Keypad chosen per generator.** Two places could disagree, and content authors
  could not change it without code.
- **Compare decimals as floats with a tolerance.** Accepts wrong answers near the
  right one and makes results depend on float rounding.

## Consequences
Prompts read naturally, wrap on small screens and can be read aloud part by part.
Word problems and bank items slot in as new variants without a data migration, and
old open problems keep working. Every new generator must build prompts from parts,
and every new keypad key must emit LaTeX the parser already reads, which the shared
samples enforce.
