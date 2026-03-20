import pytest
from pathlib import Path

from codemap.export.docx_export import export_docx


def test_export_docx_from_markdown(tmp_path):
    pytest.importorskip("docx")
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "test.md").write_text("# Test\n\nHello world\n\n## Section\n\nContent here.\n")

    output = tmp_path / "report.docx"
    export_docx(docs_dir, output)
    assert output.exists()
    assert output.stat().st_size > 0


def test_export_docx_missing_dependency(monkeypatch):
    import codemap.export.docx_export as docx_mod
    monkeypatch.setattr(docx_mod, "HAS_DOCX", False)
    with pytest.raises(ImportError, match="pip install codemap\\[docx\\]"):
        export_docx(Path("/tmp"), Path("/tmp/out.docx"))
