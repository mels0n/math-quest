# 0015. Placement: a noisy binary search over anchor skills and provisional mastery

- Status: accepted
- Date: 2026-10-15

## Context
A new player can be five or thirteen. Without placement every player starts at the first
skill, and a strong one works through weeks of material they already know before the
game offers anything new ([ADR-0010](0010-faster-mastery-ramp.md) only shortens that
inside one skill). The game collects no age, so the only signal is answers, plus an
optional "what grade are you in?".

Placement has to be short (a child should finish it in a few minutes), it has to cope
with a child who slips on something they know or guesses something they do not, and
whatever it decides must be safe to be wrong about: a child placed too high must not be
locked out of the skills they skipped, and a child placed too low must not stay there.

Content marks some skills `anchor: true`. They are the stops placement can probe; the
skill graph says what each one builds on.

## Decision
**The spine.** The anchors in the graph's topological order (declaration order breaks
ties) form a ladder, easiest first. The k8-core pack has four: adding to 10 (K),
adding to 20 (grade 1), adding with carrying (grade 2) and adding unlike fractions
(grade 5). Each probe is one problem at the anchor's middle tier, generated and checked
like a play problem. Anchors answered only with choices get a bank item; every other
anchor gets the bare generator problem, since placement measures the skill, not reading.

**The first probe.** A grade hint (K to 8) picks the first anchor of that grade band, or
the last anchor of an earlier band when the spine has none for that grade. Without a
hint the round starts at the middle anchor of the K to 2 bands, the likeliest place for
a player who gave no hint. The hint only picks the first probe; it changes nothing else.

**The search** (`engine/placement.py`, a pure function of the answers so far).
Every decision comes from the split that best agrees with the answers: the highest
passed anchor (or none) that disagrees with the fewest answers, counting correct answers
above it and misses at or below it.

- While several splits agree equally well, the next probe is the middle of their
  range. With consistent answers this is a plain binary search: a correct answer moves
  the probe up, a miss moves it down. When a later answer contradicts an earlier one,
  the range widens again and the search resumes inside it instead of stepping one anchor
  at a time.
- Once one split is best, its boundary is confirmed: the anchor below needs two more
  correct answers than misses, the anchor above two more misses than correct answers.
  The anchor furthest from its margin is asked next. So an anchor gets one problem while
  searching and a second at the boundary, more only while its answers disagree.
- The round stops after 15 answers; or when both sides are confirmed and at least 12
  were asked; or when both sides are confirmed and the split is at an end of the spine
  (nothing passed, or everything passed), where more questions would only repeat what
  is known. A child who cannot do the easiest anchor is not asked a dozen questions.
- A tie between splits at the end goes to the lower one: when placement cannot tell, it
  places lower.

**The bar.** The algorithm is tested against simulated learners on a synthetic graph
with one anchor per grade K to 8, so the test does not depend on how much content
exists. A learner at level L answers anchor A correctly with probability
`0.10 + 0.85 * logistic(2 * (L - A) + 1)`: 10% guessing, 5% slips, and in between a
logistic of how far the anchor is above what they have mastered (about 0.72 at their own
level, 0.33 one above, 0.14 two above). For true levels K, 2, 4, 6 and 8, placement
must land within one anchor of the true level in at least 95% of 1000 seeded runs, with
no hint, with a hint one grade above the level and with a hint at the level. It does in
96.8% or more of runs in every case, at about 13 questions inside the spine. The same
learners on the real four-anchor pack land within one anchor in 98% or more of runs.

**The outcome.** The frontier is the highest anchor of the best split. Every anchor up
to the frontier and all of their prerequisites, transitively, become provisionally
mastered. Taking every anchor below the frontier, not only the frontier's own
prerequisites, matters when the spine is not a single chain: the fractions anchor does
not build on two-digit addition, yet a child who passes it has passed the anchors below
it. Regions revealed are those of the provisional skills plus the frontier's region (the
first anchor's region when nothing was passed), in map order.

**Provisional mastery.** `provisional` is a new skill state, stored like the others.
It counts as mastered for the scheduler's ready set, so the skills it unlocks are
playable at once, and the skill is due for review one day later. Its lesson is not
offered before that review. Its first scored problem decides it: a correct answer makes
it mastered with the normal first review interval, a wrong one makes it learning. A
skill already mastered is never marked; a skill being learned keeps its rating and
attempts. REVIEW_DUE stays derived on read, for mastered skills only.

A skill confirmed this way has a rating with one attempt behind it, which the mastery
rule (six attempts and a top-tier streak) does not accept. Without care, its second
review would drop it back to learning even when correct. A `placed` flag on the mastery
row covers that gap: a placed mastered skill stays mastered on a correct answer, a
wrong one is judged by the normal rule, and the flag clears once the rating rule agrees.

**What placement does not touch.** No hearts, no hints, no lessons, no explanations,
and the round never says which answers were right, so the answer never leaves the
server. An unreadable or wrong-form answer is asked again and not counted, up to three
times per problem, then counts as a miss. Placement problems live only in the
`placement_runs` row (its probes in `state`, its outcome in `result`), never in
`problem_instances`: they are not solved problems, never move a rating and never enter
a session's history. A placement round is a feature slice of its own; it shares nothing
with play except the engine and the mastery table.

**Flow and retake.** After signup a new player is asked their grade (or skips the
question) and takes the round, then starts the adventure. A settings page (reached
from the play screen, and now also holding log out, which keeps the play header narrow
enough for a 320 px screen) offers a retake. Starting a round ends any unfinished one. When a retake finishes, provisional
marks that no review has confirmed are undone (a skill never played loses its row, one
played before goes back to learning) before the new outcome is applied; confirmed and
real mastery is never removed.

## Alternatives rejected
- **Plain binary search with one problem per anchor.** About four questions on nine
  anchors, but a single slip or lucky guess sends the search the wrong way for good;
  simulated learners landed within one anchor only 75 to 90% of the time.
- **Two problems per anchor, pass on both.** Spends the budget on easy anchors and still
  never recovers from an early wrong turn (67 to 79% in simulation above K).
- **Confirm by stepping one anchor at a time after a contradiction.** A contradiction
  near the top of the spine sent the boundary to the bottom, and stepping back up
  exhausted the budget; hinted rounds fell below 95%. Searching the range of equally good
  splits fixed it.
- **A Bayesian model of the learner.** Accurate, but it would assume the very model the
  test simulates, and its choices are hard to explain to a parent or a reviewer.
- **Mark only the frontier's own prerequisites.** On a spine that is not one chain,
  passing a high anchor would leave lower anchors locked.
- **Mark provisional skills as mastered outright.** Nothing would ever check a lucky
  guess, and the review schedule would treat placement as weeks of practice.
- **Provisional as a flag on a mastered row instead of a state.** Every reader of the
  state would need to know about the flag; the practice picker and the map want to show
  it as its own state anyway.
- **Ask for age, or let the grade hint set the outcome.** No personal data is collected,
  and children misreport their grade; the hint is only a head start for the search.

## Consequences
A strong new player starts at their level after about a dozen questions, and the skills
below are confirmed by ordinary reviews over the next days rather than by more testing.
A wrong placement costs little: too high, and missed reviews send skills back to
learning; too low, and the normal ramp moves on quickly. Anchors are now content
decisions with algorithmic weight: a pack should keep its anchors ordered as a ladder
and spread across grades, and adding anchors makes placement finer at no cost to the
code. The numbers (15 and 12 questions, a margin of two, one day to the first review,
three free retries) are module constants with tests, and the simulation test guards any
change to them.
