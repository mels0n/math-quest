# 0017. A planned skill graph for Number Meadows and Operation Canyon

- Status: accepted
- Date: 2026-10-17

## Context
Every skill in `skills.yaml` is bound to a registered generator
([ADR-0012](0012-content-packs.md)), and the pack refuses to load otherwise. The first
two regions need about seventy skills for kindergarten to grade 3, and generators and
teaching content arrive in batches of about ten. Writing the whole graph only as
generators would mean the shape of the curriculum (what builds on what, which skills
anchor placement, how the times tables are grouped) is never reviewed as a whole, and
each batch would decide its prerequisites without seeing the skills that come after.

Putting the skills in `skills.yaml` early is not an option. Play and placement read
that file: a skill without a generator would fail to load, and a skill without content
would be offered to children.

## Decision
**The plan is a separate file in the pack.** `planned_skills.yaml` lists the skills still
to build. Each entry has the fields of a `skills.yaml` entry without `generator` (and
without the share and vocabulary tuning, which belong to content), plus `standards` (the
Common Core codes it covers), `batch` (the build order) and an optional `unlocks`.
`load_pack` never reads the file, so nothing in it can reach play, placement or the
admin pages; its own loader (`load_planned`) and model (`PlannedSkill`) are separate.

**The plan is checked as one graph with the built skills**, by `content-lint`, which
blocks CI on errors:

- ids are unique and a built skill must leave the plan;
- every prerequisite exists, the graph has no cycle, every skill is reachable from a
  root, and a skill with no prerequisites sits in batch 1;
- no prerequisite is on a later region or grade band than the skill that needs it;
- batches run 1 to N without gaps, and every prerequisite is built in the same or an
  earlier batch (or already exists);
- anchors, in topological order, never fall to an earlier grade band, and every grade
  band of the plan has an anchor;
- at least three tiers per skill, well-formed standards codes from a grade no later than
  the skill's, and names and tier labels that are short and use no dash.

`content-report` adds the built and planned counts per region and the size of each batch.

**`unlocks` is how a plan puts a foundation under a skill that already exists.** A built
skill cannot list a planned skill as a prerequisite, because `skills.yaml` has to
resolve. A planned skill instead names the skills that gain it when it is built, and the
lint treats those as edges. When the skill is promoted, the edge is written into the
target's prerequisites in `skills.yaml`. Three exist today: `count_to_10` under
`add_within_10` and `sub_within_10`, and `teen_numbers` under `place_value_tens_ones`.
Nothing about a built skill changes until its batch is built.

**The scope is data.** The file names the regions and grade bands it covers, so the lint
holds the plan to "number meadows and operation canyon, kindergarten to grade 3" without
the engine knowing region ids. A later release plans the next regions with another scope.

**Structural choices in the graph.**

- *Region split.* Number Meadows holds counting, comparing, place value, and addition
  and subtraction within 20 and the grade 1 number work. Operation Canyon holds
  multi-digit addition and subtraction, multiplication, division, word problems,
  rounding, and the measurement, money, time and data skills that use them. A
  prerequisite never points from an earlier region to a later one.
- *Times tables are grouped by factor family, not one skill per table.* Zero, one and ten
  (a rule and a pattern), two and five (skip counting), three and four (doubling), six
  and seven, eight and nine, then eleven and twelve (breaking a factor apart). Division
  starts from sharing equally and then follows the same families in three groups (2, 5
  and 10; 3 and 4; 6 to 9), so the multiplication facts a child has support the division
  facts they unlock. Multiplication and division each end in a "mix" skill that draws on
  every table; the two mixes are anchors. Eleven and twelve go beyond the grade 3 standard (facts to 100)
  and are tagged with the grade 3 distributive property they use.
- *Anchor spine.* Eight anchors: counting to 10, adding within 10 (kindergarten); adding
  within 20 (grade 1); adding and subtracting two-digit numbers with regrouping (grade 2);
  adding three-digit numbers with regrouping, the multiplication mix and the division mix
  (grade 3). Placement probes one problem per anchor at the middle tier
  ([ADR-0015](0015-placement.md)), so each is a skill that cannot be passed without the
  ones under it. Counting to 10 is an anchor so a young child who cannot add yet still
  places somewhere above the floor.
- *Skills about problem types are separate skills.* One-step and two-step story problems
  are their own skills (grades 1 to 3) in addition to the word problems each operation
  skill draws on, because choosing the operation is a different thing to practise.
- *Fractions stay out.* They belong to Fraction Forest and its own plan.

## Alternatives rejected
- **Put the planned skills in `skills.yaml` with a `planned: true` flag.** Every reader
  of the skills (play, placement, the scheduler, the admin pages, the API) would have to
  remember to skip them, and one that forgot would offer a child a skill that cannot be
  generated. A separate file that the loader never opens cannot leak.
- **Keep the plan in a document outside the pack.** It would not be checked: a cycle, a
  prerequisite built after its dependent or a wrong grade would be found only when a
  batch hit it. In the pack it goes through the same CI as the content.
- **Let a built skill list a planned prerequisite.** It would make the pack unloadable
  until the planned skill is built, which is exactly what the plan avoids.
- **One skill per times table.** Thirteen small skills would each need a generator, a
  lesson, hints and word problems that differ only in a factor, and a child would meet
  thirteen near-identical mastery bars. The family grouping keeps each skill a distinct
  strategy.
- **A strict chain of anchors.** Requiring each anchor to depend on the previous one
  would be tidy, but the existing fraction anchor has no prerequisites, so it could never
  satisfy it. Requiring only that grade bands do not fall along the topological order
  within the plan's own regions keeps placement's ladder coherent without that.

## Consequences
- The whole curriculum of the first two regions can be reviewed, and re-ordered, before
  a generator is written; later batches start from a graph that already passed CI.
- A batch has a fixed procedure: move its skills into `skills.yaml`, add the generators,
  apply any `unlocks` edges, and remove them from the plan. Leaving a built skill in the
  plan is a lint error, so a plan cannot drift from what has shipped.
- The order of `skills.yaml` breaks ties in the topological order, and so decides the
  placement spine. New skills must be inserted so the spine keeps rising by grade band;
  the lint checks this only for the plan, so promotion keeps the plan's order.
- Counts are approximate by design: the plan has 67 planned skills beside 7 built ones in
  these regions. Splitting or merging a skill is an edit to one YAML file, reviewed in the
  pull request that makes it.
- The standards codes are carried into `skills.yaml` (an optional `standards` field), so
  coverage against the standards can be reported later without a second source.
