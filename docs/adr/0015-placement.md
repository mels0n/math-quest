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
ties) form a ladder, easiest first. The k8-core pack has six: counting to 10 and
adding to 10 (K), adding to 20 and comparing to 100 (grade 1), adding with carrying
(grade 2) and adding unlike fractions (grade 5). Each probe is one problem at the anchor's middle tier, generated and checked
like a play problem. Anchors answered only with choices get a bank item; every other
anchor gets the bare generator problem, since placement measures the skill, not reading.

**The first probe.** A grade hint (K to 8) picks the first anchor of that grade band, or
the last anchor of an earlier band when the spine has none for that grade. Without a
hint the round starts at the middle anchor of the K to 2 bands, the likeliest place for
a player who gave no hint. The hint also sets a mild prior (below); it never sets the
outcome.

**The search** (`engine/placement.py`, a pure function of the answers so far). The round
keeps a probability for every level from "no anchor passed" to "every anchor passed"
and updates it with Bayes' rule after each answer. The update uses a deliberately loose
learner model: a learner at level L answers anchor A right with probability
`0.12 + 0.80 * logistic(L - A)`, more guessing and slipping and a gentler slope than most
real learners, so a single surprising answer moves the estimate without deciding it.

- **Prior.** Flat without a hint. With a hint, each level's weight falls by 0.3 (in log
  terms) per anchor away from the hint's anchor: a head start that three or four answers
  outweigh, so a child who overstates their grade is not placed by it.
- **Next question.** When the answers point above every anchor passed so far, the next
  anchor up is asked, so a child is never placed above an anchor they were not shown.
  Otherwise the anchor whose answer is expected to leave the least uncertainty
  (posterior entropy) is asked, the lower one on a tie.
- **Stop.** After 15 answers; after 12 once the placement is 99% likely to be within one
  anchor; or as soon as "nothing passed" is 95% likely (a child who cannot do the
  easiest anchor is not asked a dozen questions), or "everything passed" is, once the
  last anchor was answered right. In practice inner levels take 15 and the ends 10 to 12.
- **Placement.** The level with the least expected cost: the right level costs nothing,
  one off costs 0.15, two or more too low costs 1 and two or more too high costs 3.
  Placing too high is worse because the child meets gaps; placing too low only means a
  few easy reviews. The placement is never above the highest anchor answered right, and
  ties go to the lower level.

**The bar.** The search is tested against simulated learners on a synthetic graph with
one anchor per grade K to 8, at every grade, with no hint, a hint at the learner's grade
and a hint one grade above, 1000 seeded runs each. A simulated learner at level L
answers anchor A right with probability `guess + (1 - guess - slip) * logistic(slope *
(L - A) + offset)`, under six models that deliberately differ from the search's own:

| Model (slope, offset, slip, guess) | no hint | hint at grade | hint one above | worst over-placement |
| --- | --- | --- | --- | --- |
| reference (1, 0, 0.05, 0.10) | 93.8% | 96.8% | 95.4% | 1.8% |
| steep (2, 1, 0.05, 0.10) | 99.1% | 99.5% | 98.4% | 1.5% |
| no guessing (2, 1, 0.05, 0) | 99.3% | 99.7% | 99.8% | 0.1% |
| slips 15% (2, 1, 0.15, 0.10) | 91.5% | 96.1% | 95.1% | 0.9% |
| slope 1.5 (1.5, 0, 0.05, 0.10) | 98.0% | 99.2% | 98.7% | 0.7% |
| guess 25%, choice anchors (2, 1, 0.05, 0.25) | 84.7% | 91.6% | 91.4% | 15.3% |

Each figure is the share placed within one anchor of the true level at the worst grade;
over-placement is the share placed two or more anchors too high. The reference model,
where a learner has even odds on their own level's anchor, must reach 95% with a hint
and keep over-placement at or below 2% at every grade, and does. Without a hint it
reaches 93.8% at worst (grade 2): that is the limit of fifteen one-problem questions for
so noisy a learner. Even a search told the true level in advance, asking every question
at that level's anchor, lands within one anchor in only about 93% of runs. The other
rows are asserted at their measured values less a small margin, so a change that makes
any of them worse fails. A hint three grades too high costs at most two points (93.6%
worst for the reference model). With a quarter of guesses landing, low-level learners
are placed too high in up to 15% of runs; choice anchors should therefore stay rare on
the spine, and the first review of each provisional skill catches what slips through.
On the real six-anchor pack, with no hint, the reference learner lands within one anchor
in 94.7% or more of runs (over-placement at most 2.4%) at about 14 questions; with the
hint of the learner's own grade, 97.9% or more (at most 1.0%) at about 14. With four
anchors the same figures were 97.4% (1.7%) and 97.7% (0.7%): a finer ladder of the same
fifteen questions costs the no-hint case a few points. Comparing to 100 is the one anchor answered with choices.

**The outcome.** The frontier is the highest anchor of the placement. Every anchor up
to the frontier and all of their prerequisites, transitively, become provisionally
mastered. Taking every anchor below the frontier, not only the frontier's own
prerequisites, matters when the spine is not a single chain: the fractions anchor does
not build on two-digit addition, yet a child who passes it has passed the anchors below
it. Regions revealed are those of the provisional skills plus the frontier's region (the
first anchor's region when nothing was passed), in map order.

**Provisional mastery.** `provisional` is a new skill state, stored like the others.
It counts as mastered for the scheduler's ready set, so the skills it unlocks are
playable at once, and the skill is due for review one day later. Its lesson is not
offered before that review. Only real progress is protected: a skill already mastered is
never marked, and neither is a skill with any scored attempt, so a retake can never hide
a skill being learned behind a provisional mark. Marking is one bulk upsert that skips
those rows.

**Confirmation.** A provisional skill is decided by its first scored problem that can
confirm it: the generator's own problem (not a bank item, whose answer might be guessed
from the choices; a skill answered only by choices has nothing else) at the placement
probe's tier or above. Reviews and practice problems of a provisional skill are issued
that way, so in practice the first review decides it. A correct answer makes it
mastered with the normal first review interval; a wrong one makes it learning; a correct
answer on a problem that cannot confirm it leaves it provisional and still due. Players
see a provisional skill past its review date as review due, like a mastered one, so it
counts toward "my weak spots".

A skill confirmed this way has a rating with one attempt behind it, which the mastery
rule (six attempts and a top-tier streak) does not accept. A `placed` flag on the
mastery row covers that gap: a placed mastered skill stays mastered on a correct answer,
and, like a real mastered skill's slip, its first miss among the last six outcomes only
resets the review interval to one day; a second miss in that window sends it back to
learning. The flag clears once the rating rule agrees, and the normal rule applies from
then on. Seeding a fake history at confirmation was considered instead, but the rating's
streak bonus makes a single miss after a long seeded streak drop the rating below the
mastery line, so the seed would not survive a slip either, and invented attempts would
mislead every later reader of the row.

**What placement does not touch.** No hearts, no hints, no lessons, no explanations,
and the round never says which answers were right, so the answer never leaves the
server. An unreadable or wrong-form answer is asked again and not counted, up to three
times per problem, then counts as a miss. Placement problems live only in the
`placement_runs` row (its probes in `state`, its outcome in `result`), never in
`problem_instances`: they are not solved problems, never move a rating and never enter
a session's history. A placement round is a feature slice of its own; it shares nothing
with play except the engine and the mastery table.

**Flow and retake.** After signup a new player is asked their grade (or skips the
question) and takes the round, then starts the adventure. The round is called "Find my
level" on screen: "warm-up" already names the prerequisite problems inserted during play
([ADR-0014](0014-teaching-flow.md)). Its progress reads "Puzzle 3", not "3 of up to 15",
since the round may end early. A settings page (reached from the play screen, and also
holding log out, which keeps the play header narrow enough for a 320 px screen) offers
"Find my level again". Starting a round ends any unfinished one, under a lock on the
player's row so two starts at once cannot both stay open. Rounds are limited to six
starts an hour per player, and a completed round cannot be retaken within ten minutes
(409 `retake_too_soon`, shown as a friendly line), since back-to-back retakes only
reshuffle provisional marks. When a retake finishes, provisional marks that no review
has confirmed are undone (a skill never played loses its row, one played before goes
back to learning) before the new outcome is applied; confirmed and real mastery, and
any skill with real attempts, is never touched.

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
- **The first version: the split that disagrees with the fewest answers, confirmed by a
  margin of two.** It met the bar for the steep learner it was tuned on, but for the
  reference learner it landed within one anchor in only 83 to 89% of runs, mostly too
  low, because it counted every answer as equally decisive.
- **A Bayesian search that assumes the simulated learners' own model.** It would pass its
  own test by construction. The search uses a looser model than any simulated one and is
  tested against six, which answers the earlier objection that a Bayesian search only
  proves the model it assumes. Its choices are still explainable: "the answers point
  above what you have shown, so we ask the next one up".
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
code. The numbers (15 and 12 questions, the search's learner model, the hint prior, the
stopping confidences and costs, one day to the first review, three free retries) are
module constants with tests, and the simulation matrix guards any change to them.
