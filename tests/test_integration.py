"""Full pipeline integration test: scan → render → doc → export"""
import json
from pathlib import Path

from click.testing import CliRunner
from codemap.cli import main

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def test_full_pipeline(tmp_path):
    runner = CliRunner()

    # 1. Scan
    scan_file = tmp_path / "scan.json"
    result = runner.invoke(main, ["scan", str(FIXTURE_DIR), "-o", str(scan_file), "--target", "db"])
    assert result.exit_code == 0

    # 2. Render ERD
    erd_file = tmp_path / "erd.mmd"
    result = runner.invoke(main, ["render", "erd", "--from", str(scan_file), "--format", "mermaid", "-o", str(erd_file)])
    assert result.exit_code == 0
    assert "erDiagram" in erd_file.read_text()

    # 3. Doc table-spec
    doc_file = tmp_path / "table-spec.md"
    result = runner.invoke(main, ["doc", "table-spec", "--from", str(scan_file), "-o", str(doc_file)])
    assert result.exit_code == 0
    assert "# 테이블 정의서" in doc_file.read_text()

    # 4. Export xlsx
    xlsx_file = tmp_path / "table-spec.xlsx"
    result = runner.invoke(main, ["export", "xlsx", "--from", str(scan_file), "--type", "table-spec", "-o", str(xlsx_file)])
    assert result.exit_code == 0
    assert xlsx_file.exists()


def test_scan_multi_target(tmp_path):
    """Verify comma-separated --target works."""
    scan_file = tmp_path / "scan.json"
    runner = CliRunner()
    result = runner.invoke(main, ["scan", str(FIXTURE_DIR), "-o", str(scan_file), "--target", "db,api"])
    assert result.exit_code == 0
    data = json.loads(scan_file.read_text())
    assert len(data["database"]["tables"]) > 0


def test_render_all(tmp_path):
    """Verify render all generates all diagram types."""
    scan_file = tmp_path / "scan.json"
    runner = CliRunner()
    runner.invoke(main, ["scan", str(FIXTURE_DIR), "-o", str(scan_file), "--target", "db"])

    output_dir = tmp_path / "diagrams"
    result = runner.invoke(main, [
        "render", "all", "--from", str(scan_file), "--format", "mermaid", "-o", str(output_dir)
    ])
    assert result.exit_code == 0


def test_doc_all(tmp_path):
    """Verify doc all generates all document types."""
    scan_file = tmp_path / "scan.json"
    runner = CliRunner()
    runner.invoke(main, ["scan", str(FIXTURE_DIR), "-o", str(scan_file), "--target", "db"])

    output_dir = tmp_path / "docs"
    result = runner.invoke(main, [
        "doc", "all", "--from", str(scan_file), "-o", str(output_dir)
    ])
    assert result.exit_code == 0


def test_full_pipeline_no_ai(tmp_path):
    """Full pipeline with --no-ai should work identically to before."""
    runner = CliRunner()
    out_dir = tmp_path / "output"
    result = runner.invoke(main, [
        "--no-ai", "generate", str(FIXTURE_DIR),
        "-o", str(out_dir), "--target", "db",
    ])
    assert result.exit_code == 0
    assert (out_dir / "scan.json").exists()
    assert (out_dir / "docs" / "table-spec.md").exists()
    assert "# 테이블 정의서" in (out_dir / "docs" / "table-spec.md").read_text()
