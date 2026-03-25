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


def test_default_config_has_ai(monkeypatch):
    monkeypatch.setenv("CODEMAP_AI_URL", "http://test:11434")
    monkeypatch.setenv("CODEMAP_AI_MODEL", "test-model")
    from codemap.config import AiConfig
    cfg = AiConfig()
    assert cfg.enabled is True
    assert cfg.base_url == "http://test:11434"
    assert cfg.model == "test-model"
    assert cfg.language == "ko"


def test_default_config_ai_empty_without_env(monkeypatch):
    monkeypatch.delenv("CODEMAP_AI_URL", raising=False)
    monkeypatch.delenv("CODEMAP_AI_MODEL", raising=False)
    from codemap.config import AiConfig
    cfg = AiConfig()
    assert cfg.base_url == ""
    assert cfg.model == ""


def test_load_config_with_ai_override(tmp_path):
    config_dir = tmp_path / ".codemap"
    config_dir.mkdir()
    config_file = config_dir / "config.yaml"
    config_file.write_text(
        "ai:\n  enabled: false\n  model: qwen3.5:9b\n"
    )
    cfg = load_config(tmp_path)
    assert cfg.ai.enabled is False
    assert cfg.ai.model == "qwen3.5:9b"
    assert cfg.ai.language == "ko"


def test_load_config_without_ai_section(tmp_path):
    config_dir = tmp_path / ".codemap"
    config_dir.mkdir()
    config_file = config_dir / "config.yaml"
    config_file.write_text("project:\n  name: my-proj\n")
    cfg = load_config(tmp_path)
    assert cfg.ai.enabled is True
    assert cfg.ai.language == "ko"
