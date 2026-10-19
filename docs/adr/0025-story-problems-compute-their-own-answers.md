# 0025. Story problems to 20 retell the numbers and compute their own answers

- Status: accepted
- Date: 2026-10-19

## Context
A word template normally retells the generator's numbers and keeps the generator's answer
([ADR-0012](0012-content-packs.md)), so the hints, explanations and mistake feedback written
for the generator apply to it. That works for a skill with one operation: every template of
Add to 20 is an adding story.

Story Problems to 20 (1.OA.A.1) is the skill of telling which operation a story needs. Its
stories add to, take from, put together, take apart, compare, and hide the change or the
start (answers that are sums for some shapes and differences for others, from the same two
numbers). A template has no way to ask for a shape, so a template that kept the generator's
answer would be wrong for every draw that asked another shape.

## Decision
- **The generator gives two numbers.** `a` is more than `b`, and `a + b` is at most 20, so
  both a sum and a difference stay within 20 whatever the shape. Its own typed problems tell
  a story in a fixed shape per tier (result unknown, then put together, take apart and
  compare, then the change or the start unknown) and have hints and mistake feedback.
- **Every word template computes its own answer** (`answer_from: expression`, over `a` and
  `b`), so it can tell any shape. A template id starts with its shape and no shape has more
  than two templates, so the set stays varied. A test pins each shape to its expression and
  keywords, and renders every template for many numbers to check agreement with 1.
- **Hints hand over no operation.** The first two hints and all feedback and explanations
  for the skill say nothing about adding or taking away; a test enforces it.

## Alternatives rejected
- **Tag templates with a shape and match it to the generator's.** It keeps hints on word
  problems, but it adds a schema field, a filter in template choice and a second preview
  path in the admin area, for one skill. It is the right follow-up if hints on story
  variants prove missed.
- **Draw only one shape per template list and split the skill.** It would make the skill
  about adding stories or taking-away stories, which is what the plan does not want
  children to rely on.
- **Keep the generator's answer and write only add stories.** It would not teach telling
  the operation.

## Consequences
A learner who gets a story variant has no hints or explanations for it, as with a bank
item ([ADR-0012](0012-content-packs.md)); the typed stories of the generator, 60% of the
draws, have them. Mistake feedback applies to the typed stories only. Both numbers of every
story are shown, so a learner can always work the problem out.
