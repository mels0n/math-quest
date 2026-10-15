"""Visual models: the pictures lessons and explanations draw, one params schema per kind.

A visual is ``{kind, params}``; ``kind`` picks the params model, so a misspelt or
missing parameter, or a number out of range, is a load error naming the field. A
numeric parameter is either a whole number or a template string (``"{big}"``,
``"{{= a + b }}"``) filled in from the problem's values when the visual is rendered.
Range checks run on the whole numbers known when the pack loads; ``resolve`` runs them
again once every template is filled in, so a visual that only goes out of range for
some problem's numbers fails there (the content lint renders every skill's teaching
text for many seeds, so it reports that case too).

What each kind draws (the frontend's ``shared/visuals`` components):

``number_line``
    Ticks from ``min`` to ``max`` (at most ``MAX_LINE_SPAN`` apart). An optional
    ``start`` point, then ``jumps``: a list of jump sizes (negative jumps go left), or
    one number ``n`` meaning ``|n|`` jumps of one in the direction of its sign. An
    optional ``end`` point is marked as the landing spot.
``base_ten``
    ``hundreds`` flats, ``tens`` rods and ``ones`` cubes.
``fraction_bars``
    One to four bars, each cut into ``parts`` equal parts with ``shaded`` of them
    filled.
``area_model``
    A rectangle split into ``rows`` by ``cols`` pieces (the place-value parts of each
    factor), each piece labelled with its product when ``show_products``.
``algebra_tiles``
    ``x2`` square tiles, ``x`` long tiles and ``units`` small tiles; a negative count
    draws that many negative tiles.
``array``
    ``rows`` by ``cols`` dots.
``clock``
    An analog clock showing ``hour``:``minute``.
``money``
    Counts of ``dollars``, ``quarters``, ``dimes``, ``nickels`` and ``pennies``.
"""

from typing import Annotated, Literal, Self, get_args

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    PlainValidator,
    ValidationError,
    model_validator,
)

from mathquest.engine.templates import check_template

MAX_LINE_SPAN = 100
MAX_PIECES = 3
MAX_BARS = 4
MAX_PARTS = 12
MAX_GRID = 12
MAX_TILES = 10
MAX_BLOCKS = 20
MAX_COINS = 10


def _num(value: object) -> int | str:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, str) and value:
        return check_template(value)
    raise ValueError("expected a whole number or a template")


Num = Annotated[int | str, PlainValidator(_num)]
"""A whole number, or a template that renders to one."""


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def _known(*values: Num | None) -> tuple[int, ...] | None:
    """The values as ints when every one is a whole number; None while any is a template."""
    if any(isinstance(v, str) for v in values):
        return None
    return tuple(v for v in values if isinstance(v, int))


def _between(name: str, value: Num | None, lo: int, hi: int) -> None:
    if isinstance(value, int) and not lo <= value <= hi:
        raise ValueError(f"{name} must be from {lo} to {hi}, not {value}")


class NumberLineParams(_Model):
    min: Num = 0
    max: Num = 10
    start: Num | None = None
    jumps: Num | tuple[Num, ...] = ()
    end: Num | None = None

    def steps(self) -> tuple[int, ...] | None:
        """Each jump's size, or None while any is a template."""
        if isinstance(self.jumps, str):
            return None
        if isinstance(self.jumps, int):
            sign = 1 if self.jumps >= 0 else -1
            return (sign,) * abs(self.jumps)
        known = _known(*self.jumps)
        return None if known is None else known

    @model_validator(mode="after")
    def _in_range(self) -> Self:
        bounds = _known(self.min, self.max)
        if bounds is None:
            return self
        lo, hi = bounds
        if not 0 < hi - lo <= MAX_LINE_SPAN:
            raise ValueError(f"max must be above min by 1 to {MAX_LINE_SPAN}")
        _between("start", self.start, lo, hi)
        _between("end", self.end, lo, hi)
        steps = self.steps()
        if steps and self.start is None:
            raise ValueError("jumps need a start")
        if steps and isinstance(self.start, int):
            at = self.start
            for step in steps:
                if step == 0:
                    raise ValueError("a jump of 0 goes nowhere")
                at += step
                _between("a jump's landing point", at, lo, hi)
        if isinstance(self.jumps, int) and abs(self.jumps) > MAX_LINE_SPAN:
            raise ValueError(f"at most {MAX_LINE_SPAN} jumps")
        return self


class BaseTenParams(_Model):
    hundreds: Num = 0
    tens: Num = 0
    ones: Num = 0

    @model_validator(mode="after")
    def _in_range(self) -> Self:
        for name in ("hundreds", "tens", "ones"):
            _between(name, getattr(self, name), 0, MAX_BLOCKS)
        if _known(self.hundreds, self.tens, self.ones) == (0, 0, 0):
            raise ValueError("draw at least one block")
        return self


class FractionBar(_Model):
    parts: Num
    shaded: Num = 0

    @model_validator(mode="after")
    def _in_range(self) -> Self:
        _between("parts", self.parts, 1, MAX_PARTS)
        top = self.parts if isinstance(self.parts, int) else MAX_PARTS
        _between("shaded", self.shaded, 0, top)
        return self


class FractionBarsParams(_Model):
    bars: Annotated[tuple[FractionBar, ...], Field(min_length=1, max_length=MAX_BARS)]


Pieces = Annotated[tuple[Num, ...], Field(min_length=1, max_length=MAX_PIECES)]


class AreaModelParams(_Model):
    rows: Pieces
    cols: Pieces
    show_products: bool = True

    @model_validator(mode="after")
    def _in_range(self) -> Self:
        for value in (*self.rows, *self.cols):
            _between("a piece", value, 1, 1000)
        return self


class AlgebraTilesParams(_Model):
    x2: Num = 0
    x: Num = 0
    units: Num = 0

    @model_validator(mode="after")
    def _in_range(self) -> Self:
        for name in ("x2", "x", "units"):
            _between(name, getattr(self, name), -MAX_TILES, MAX_TILES)
        if _known(self.x2, self.x, self.units) == (0, 0, 0):
            raise ValueError("draw at least one tile")
        return self


class ArrayParams(_Model):
    rows: Num
    cols: Num

    @model_validator(mode="after")
    def _in_range(self) -> Self:
        _between("rows", self.rows, 1, MAX_GRID)
        _between("cols", self.cols, 1, MAX_GRID)
        return self


class ClockParams(_Model):
    hour: Num
    minute: Num = 0

    @model_validator(mode="after")
    def _in_range(self) -> Self:
        _between("hour", self.hour, 1, 12)
        _between("minute", self.minute, 0, 59)
        return self


class MoneyParams(_Model):
    dollars: Num = 0
    quarters: Num = 0
    dimes: Num = 0
    nickels: Num = 0
    pennies: Num = 0

    @model_validator(mode="after")
    def _in_range(self) -> Self:
        names = ("dollars", "quarters", "dimes", "nickels", "pennies")
        for name in names:
            _between(name, getattr(self, name), 0, MAX_COINS)
        if _known(*(getattr(self, n) for n in names)) == (0, 0, 0, 0, 0):
            raise ValueError("draw at least one coin or bill")
        return self


class NumberLine(_Model):
    kind: Literal["number_line"]
    params: NumberLineParams = NumberLineParams()


class BaseTen(_Model):
    kind: Literal["base_ten"]
    params: BaseTenParams


class FractionBars(_Model):
    kind: Literal["fraction_bars"]
    params: FractionBarsParams


class AreaModel(_Model):
    kind: Literal["area_model"]
    params: AreaModelParams


class AlgebraTiles(_Model):
    kind: Literal["algebra_tiles"]
    params: AlgebraTilesParams


class ArrayGrid(_Model):
    kind: Literal["array"]
    params: ArrayParams


class Clock(_Model):
    kind: Literal["clock"]
    params: ClockParams


class Money(_Model):
    kind: Literal["money"]
    params: MoneyParams


Visual = Annotated[
    NumberLine | BaseTen | FractionBars | AreaModel | AlgebraTiles | ArrayGrid | Clock | Money,
    Field(discriminator="kind"),
]
"""A picture drawn next to text, discriminated by ``kind``."""

VisualModel = (
    NumberLine | BaseTen | FractionBars | AreaModel | AlgebraTiles | ArrayGrid | Clock | Money
)
VisualKind = Literal[
    "number_line", "base_ten", "fraction_bars", "area_model", "algebra_tiles", "array", "clock",
    "money",
]  # fmt: skip
VISUAL_KINDS: tuple[VisualKind, ...] = get_args(VisualKind)


class UnresolvedVisual(ValueError):
    """A visual whose filled-in params are not whole numbers or are out of range."""


def _templates_left(value: JsonValue) -> bool:
    if isinstance(value, str):
        return True
    if isinstance(value, list):
        return any(_templates_left(v) for v in value)
    if isinstance(value, dict):
        return any(_templates_left(v) for v in value.values())
    return False


def resolve(visual: VisualModel, params: dict[str, JsonValue]) -> VisualModel:
    """``visual`` with ``params`` (its templates filled in), checked again in full.

    Raises UnresolvedVisual when a parameter is still not a whole number or a range
    check fails for these numbers.
    """
    if _templates_left(params):
        raise UnresolvedVisual(f"{visual.kind}: a parameter did not render to a whole number")
    try:
        return type(visual).model_validate({"kind": visual.kind, "params": params})
    except ValidationError as err:
        first = err.errors()[0]
        raise UnresolvedVisual(f"{visual.kind}: {first['msg']}") from None
