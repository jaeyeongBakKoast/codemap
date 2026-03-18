# tests/test_config.py
import os
from pathlib import Path

from codemap.config import load_config, CodemapConfig, DEFAULT_CONFIG


def test_default_config():
    cfg = DEFAULT_CONFIG
    assert cfg.project.name == ""
    assert cfg.scan.database.paths == ["doc/database/**/*.sql"]
    assert cfg.scan.backend.framework == "spring"


def test_load_config_from_file(tmp_path):
    config_dir = tmp_path / ".codemap"
    config_dir.mkdir()
    config_file = config_dir / "config.yaml"
    config_file.write_text(
        "project:\n  name: my-proj\nscan:\n  database:\n    paths: ['db/*.sql']\n"
    )
    cfg = load_config(tmp_path)
    assert cfg.project.name == "my-proj"
    assert cfg.scan.database.paths == ["db/*.sql"]
    # Non-overridden fields keep defaults
    assert cfg.scan.backend.framework == "spring"


def test_load_config_missing_file(tmp_path):
    cfg = load_config(tmp_path)
    assert cfg.project.name == ""
    assert cfg.scan.database.paths == ["doc/database/**/*.sql"]


def test_load_config_from_fixture():
    fixture_dir = Path(__file__).parent / "fixtures"
    cfg = load_config(fixture_dir, config_filename="config.yaml")
    assert cfg.project.name == "test-project"
