"""The content-lint command: exit status and output format."""

import shutil
from pathlib import Path

import pytest

from mathquest.cli import content_lint
from tests.engine.content.packbuilder import CONTENT, base, write


def _content_dir(tmp_path: Path) -> Path:
    root = tmp_path / "content"
    (root / "lint").mkdir(parents=True)
    shutil.copy(CONTENT / "slots.yaml", root / "slots.yaml")
    shutil.copy(CONTENT / "lint" / "k2_words.txt", root / "lint" / "k2_words.txt")
    return root


def test_real_pack_passes(capsys: pytest.CaptureFixture[str]) -> None:
    assert content_lint.main([str(CONTENT / "packs" / "k8-core")]) == 0
    assert "0 errors" in capsys.readouterr().out


def test_errors_fail_and_print_file_path_rule(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    files = base()
    files["hints/alpha.yaml"]["levels"][0]["text_template"] = "Put {a} and {b} — together."
    pack = write(_content_dir(tmp_path) / "packs", files)
    assert content_lint.main([str(pack)]) == 1
    out = capsys.readouterr().out
    assert f"error: {pack}/hints/alpha.yaml:levels[0].text_template: dashes: " in out
    assert "1 errors, 0 warnings" in out


def test_a_pack_that_does_not_load_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    files = base()
    files["pack.yaml"]["version"] = "one"
    pack = write(_content_dir(tmp_path) / "packs", files)
    assert content_lint.main([str(pack)]) == 1
    assert "pack.yaml: version" in capsys.readouterr().out
