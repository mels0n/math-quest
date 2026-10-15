"""Admin content preview: the live pack's coverage, and every item of a skill rendered.

Everything is read from the catalog the app loaded at boot (passed in by the caller);
nothing here reads files. Rendering goes through the engine's own renderers and the
skill's ``SkillSource``, so the preview shows exactly what a learner would get for the
same seed and tier, plus the answers.
"""

from collections.abc import Callable

from mathquest.engine.catalog import Catalog, SkillSource
from mathquest.engine.content.coverage import SkillCoverage, pack_coverage, skill_coverage
from mathquest.engine.content.schema import Explanations, Visual
from mathquest.engine.teaching import (
    render_explanations,
    render_feedback,
    render_hints,
    render_lesson,
)
from mathquest.engine.templates import TemplateError
from mathquest.engine.transport import answer_latex, latex, prompt_out
from mathquest.engine.types import Generator, Problem, Variant
from mathquest.features.admin.content_schema import (
    ApproachOut,
    BankItemOut,
    ContentOverview,
    GapOut,
    LessonOut,
    LessonScreenOut,
    MisconceptionOut,
    PackOut,
    ProblemPreview,
    RegionCoverageOut,
    SkillCoverageOut,
    SkillPreview,
    VisualOut,
    WordTemplateOut,
)
from mathquest.shared.errors import Invalid, NotFound

SAMPLE_SEEDS = (1, 2, 3)
"""Seeds shown when the admin does not pick one."""


def _visual(visual: Visual | None) -> VisualOut | None:
    return None if visual is None else VisualOut(kind=visual.kind, params=dict(visual.params))


def _coverage(coverage: SkillCoverage) -> SkillCoverageOut:
    return SkillCoverageOut(
        skill_id=coverage.skill_id,
        name=coverage.name,
        tiers=coverage.tiers,
        misconceptions=coverage.misconceptions,
        word_templates=coverage.word_templates,
        bank_items=coverage.bank_items,
        lesson=coverage.lesson,
        hints=coverage.hints,
        explanations=coverage.explanations,
        gaps=[GapOut(field=g.field, have=g.have, want=g.want) for g in coverage.gaps],
    )


def _registry(catalog: Catalog) -> dict[str, Generator]:
    return {s.skill.generator: s.generator for s in catalog.sources.values()}


def overview(catalog: Catalog) -> ContentOverview:
    """The live pack with its version and per-skill coverage, by region in map order."""
    pack = catalog.pack
    coverage = pack_coverage(pack, _registry(catalog))
    return ContentOverview(
        packs=[
            PackOut(
                id=pack.id,
                title=pack.title,
                version=pack.version,
                live=True,
                complete_regions=list(pack.complete_regions),
                regions=[
                    RegionCoverageOut(
                        region_id=r.region_id,
                        name=r.name,
                        complete=r.complete,
                        skills=[_coverage(s) for s in r.skills],
                    )
                    for r in coverage.regions
                ],
            )
        ]
    )


def _preview(
    source: SkillSource,
    seed: int,
    tier: int,
    variant: Variant = "bare",
    template_id: str | None = None,
) -> ProblemPreview:
    try:
        problem = source.generate(seed, tier, variant, template_id)
    except TemplateError as err:
        return ProblemPreview(
            seed=seed,
            tier=tier,
            prompt=[],
            answer_latex=None,
            choices=None,
            correct_choice=None,
            misconceptions=[],
            error=str(err),
        )
    return _problem(problem, None)


def _problem(problem: Problem, explanations: Explanations | None) -> ProblemPreview:
    misconceptions: list[MisconceptionOut] = []
    for m in problem.misconceptions:
        feedback = None if explanations is None else render_feedback(explanations, problem, m.key)
        misconceptions.append(
            MisconceptionOut(
                key=m.key,
                answer_latex=latex(m.answer),
                feedback=None if feedback is None else prompt_out(feedback),
            )
        )
    return ProblemPreview(
        seed=problem.seed,
        tier=problem.tier,
        prompt=prompt_out(problem.prompt),
        answer_latex=answer_latex(problem),
        choices=None if problem.choices is None else [prompt_out(c) for c in problem.choices],
        correct_choice=problem.correct_choice,
        misconceptions=misconceptions,
    )


def _section[T](name: str, errors: list[str], render: Callable[[], T]) -> T | None:
    try:
        return render()
    except TemplateError as err:
        errors.append(f"{name}: {err}")
        return None


def skill_preview(
    catalog: Catalog, skill_id: str, *, seed: int | None = None, tier: int = 0
) -> SkillPreview:
    """Every item of ``skill_id`` rendered for ``seed`` (default: a few sample seeds).

    NotFound for an unknown skill; Invalid("tier") for a tier the skill does not have.
    Hints, explanations and misconception feedback are rendered for the first seed's
    bare problem.
    """
    if skill_id not in catalog.sources:
        raise NotFound()
    source = catalog.source(skill_id)
    skill = source.skill
    if not 0 <= tier < len(skill.tiers):
        raise Invalid("tier")
    pack = catalog.pack
    seeds: list[int] = [seed] if seed is not None else list(SAMPLE_SEEDS)
    errors: list[str] = []
    explanations = pack.explanations.get(skill_id)
    bare = [source.generate(s, tier) for s in seeds]
    problems: list[ProblemPreview] = []
    for problem in bare:
        shown = _section("feedback", errors, lambda p=problem: _problem(p, explanations))
        problems.append(shown if shown is not None else _problem(problem, None))
    focus = bare[0]

    lesson = None
    if (written := pack.lessons.get(skill_id)) is not None:
        rendered = _section("lesson", errors, lambda: render_lesson(written))
        if rendered is not None:
            lesson = LessonOut(
                screens=[
                    LessonScreenOut(
                        title=s.title, body=prompt_out(s.body), visual=_visual(s.visual)
                    )
                    for s in rendered.screens
                ],
                worked_prompt=prompt_out(rendered.worked_prompt),
                worked_steps=[prompt_out(step) for step in rendered.worked_steps],
                try_it_tier=rendered.try_it_tier,
                try_it_seed=rendered.try_it_seed,
            )

    hints = None
    if (ladder := pack.hints.get(skill_id)) is not None:
        levels = _section("hints", errors, lambda: render_hints(ladder, focus))
        hints = None if levels is None else [prompt_out(level) for level in levels]

    approaches = None
    if explanations is not None:
        rendered_approaches = _section(
            "explanations", errors, lambda: render_explanations(explanations, focus)
        )
        if rendered_approaches is not None:
            approaches = [
                ApproachOut(style=a.style, body=prompt_out(a.body), visual=_visual(a.visual))
                for a in rendered_approaches
            ]

    word_templates: list[WordTemplateOut] = []
    if source.word_problems is not None:
        for template in source.word_problems.templates:
            word_templates.append(
                WordTemplateOut(
                    id=template.id,
                    grade_band=template.grade_band,
                    answer_from=template.answer_from,
                    samples=[_preview(source, s, tier, "word", template.id) for s in seeds],
                )
            )
    bank_items: list[BankItemOut] = []
    if source.bank is not None:
        for item in source.bank.items:
            bank_items.append(
                BankItemOut(
                    id=item.id,
                    kind=item.answer.kind,
                    sample=_preview(source, seeds[0], tier, "bank", item.id),
                )
            )

    return SkillPreview(
        skill_id=skill.id,
        name=skill.name,
        region=skill.region,
        grade_band=skill.grade_band,
        keypad=skill.keypad,
        tier_labels=[t.label for t in skill.tiers],
        tier=tier,
        seeds=seeds,
        coverage=_coverage(skill_coverage(pack, skill, source.generator)),
        problems=problems,
        lesson=lesson,
        hints=hints,
        explanations=approaches,
        word_templates=word_templates,
        bank_items=bank_items,
        errors=errors,
    )
