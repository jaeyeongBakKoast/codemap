import json
from pathlib import Path

from click.testing import CliRunner

from codemap.cli import main

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def test_cli_scan_outputs_json(tmp_path):
    output_file = tmp_path / "scan.json"
    runner = CliRunner()
    result = runner.invoke(main, ["scan", str(FIXTURE_DIR), "-o", str(output_file), "--target", "db"])
    assert result.exit_code == 0
    assert output_file.exists()
    data = json.loads(output_file.read_text())
    assert data["version"] == "1.0"
    assert "database" in data


def test_cli_scan_target_db(tmp_path):
    output_file = tmp_path / "scan.json"
    runner = CliRunner()
    result = runner.invoke(main, ["scan", str(FIXTURE_DIR), "-o", str(output_file), "--target", "db"])
    assert result.exit_code == 0
    data = json.loads(output_file.read_text())
    assert len(data["database"]["tables"]) > 0


def test_cli_scan_stdout():
    runner = CliRunner()
    result = runner.invoke(main, ["scan", str(FIXTURE_DIR), "--target", "db"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "database" in data


def test_cli_version():
    runner = CliRunner()
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.output


# --- render command tests ---

def test_cli_render_erd_mermaid(tmp_path):
    scan_file = tmp_path / "scan.json"
    runner = CliRunner()
    runner.invoke(main, ["scan", str(FIXTURE_DIR), "-o", str(scan_file), "--target", "db"])

    output_file = tmp_path / "erd.mmd"
    result = runner.invoke(main, ["render", "erd", "--from", str(scan_file), "--format", "mermaid", "-o", str(output_file)])
    assert result.exit_code == 0
    content = output_file.read_text()
    assert "erDiagram" in content


def test_cli_render_erd_drawio(tmp_path):
    scan_file = tmp_path / "scan.json"
    runner = CliRunner()
    runner.invoke(main, ["scan", str(FIXTURE_DIR), "-o", str(scan_file), "--target", "db"])

    output_file = tmp_path / "erd.drawio"
    result = runner.invoke(main, ["render", "erd", "--from", str(scan_file), "--format", "drawio", "-o", str(output_file)])
    assert result.exit_code == 0
    content = output_file.read_text()
    assert "mxfile" in content


# --- doc command tests ---

def test_cli_doc_table_spec(tmp_path):
    scan_file = tmp_path / "scan.json"
    runner = CliRunner()
    runner.invoke(main, ["scan", str(FIXTURE_DIR), "-o", str(scan_file), "--target", "db"])

    output_file = tmp_path / "table-spec.md"
    result = runner.invoke(main, ["doc", "table-spec", "--from", str(scan_file), "-o", str(output_file)])
    assert result.exit_code == 0
    content = output_file.read_text()
    assert "# 테이블 정의서" in content


# --- export command tests ---

def test_cli_export_xlsx(tmp_path):
    scan_file = tmp_path / "scan.json"
    runner = CliRunner()
    runner.invoke(main, ["scan", str(FIXTURE_DIR), "-o", str(scan_file), "--target", "db"])

    output_file = tmp_path / "table-spec.xlsx"
    result = runner.invoke(main, [
        "export", "xlsx", "--from", str(scan_file),
        "--type", "table-spec", "-o", str(output_file)
    ])
    assert result.exit_code == 0
    assert output_file.exists()


# --- generate command tests ---

def test_cli_generate(tmp_path):
    output_dir = tmp_path / "output"
    runner = CliRunner()
    result = runner.invoke(main, [
        "generate", str(FIXTURE_DIR), "-o", str(output_dir),
        "--target", "db", "--format", "mermaid"
    ])
    assert result.exit_code == 0
    assert (output_dir / "diagrams").exists() or any(output_dir.rglob("*.mmd"))
    assert any(output_dir.rglob("*.md"))


def test_cli_generate_with_export(tmp_path):
    output_dir = tmp_path / "output"
    runner = CliRunner()
    result = runner.invoke(main, [
        "generate", str(FIXTURE_DIR), "-o", str(output_dir),
        "--target", "db", "--format", "mermaid", "--export", "xlsx"
    ])
    assert result.exit_code == 0
    assert any(output_dir.rglob("*.xlsx"))
