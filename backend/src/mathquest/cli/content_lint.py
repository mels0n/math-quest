"""``content-lint``: lint content packs and exit non-zero on any error.

Usage: ``uv run content-lint [PACK_DIR ...]`` (run in ``backend/``; default: every pack
under ``content/packs``). Each pack is loaded with the validating loader, then linted
against the built-in generators, the shared slot lists (``content/slots.yaml``) and the
early-reader word list (``content/lint/k2_words.txt``), both found two levels above the
pack directory. Every finding is printed as ``level: file:path: rule: message``.
"""

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from mathquest.engine.content import ContentError, load_pack, load_slots
from mathquest.engine.content.lint import errors, lint, load_word_list
from mathquest.engine.generators import all_generators

DEFAULT_PACKS = Path("content") / "packs"
WORD_LIST = Path("lint") / "k2_words.txt"


def pack_dirs(given: Sequence[str]) -> list[Path]:
    if given:
        return [Path(p) for p in given]
    return sorted(p for p in DEFAULT_PACKS.iterdir() if (p / "pack.yaml").is_file())


def lint_dir(pack_dir: Path) -> tuple[int, int]:
    """Lint one pack directory, printing findings. Returns (errors, warnings)."""
    content_dir = pack_dir.resolve().parent.parent
    try:
        pack = load_pack(pack_dir)
        slots = load_slots(content_dir / "slots.yaml")
    except ContentError as err:
        print(f"error: {pack_dir}/{err}")
        return 1, 0
    words = load_word_list(content_dir / WORD_LIST)
    findings = lint(pack, all_generators(), slots=slots, words=words)
    for finding in sorted(findings, key=lambda f: f.level != "error"):
        print(f"{finding.level}: {pack_dir}/{finding}")
    failed = len(errors(findings))
    return failed, len(findings) - failed


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="content-lint", description="Lint content packs.")
    parser.add_argument("packs", nargs="*", help="pack directories (default: content/packs/*)")
    args = parser.parse_args(argv)
    total_errors = 0
    for pack_dir in pack_dirs(args.packs):
        failed, warned = lint_dir(pack_dir)
        print(f"{pack_dir}: {failed} errors, {warned} warnings")
        total_errors += failed
    return 1 if total_errors else 0


if __name__ == "__main__":
    sys.exit(main())
