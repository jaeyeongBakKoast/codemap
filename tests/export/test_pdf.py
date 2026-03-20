import pytest
from pathlib import Path

from codemap.export.pdf import export_pdf


def test_export_pdf_from_markdown(tmp_path):
    pytest.importorskip("weasyprint")
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "test.md").write_text("# Test\n\nHello world\n")

    output = tmp_path / "report.pdf"
    export_pdf(docs_dir, output)
    assert output.exists()
    assert output.stat().st_size > 0


def test_export_pdf_missing_weasyprint(monkeypatch):
    import codemap.export.pdf as pdf_mod
    monkeypatch.setattr(pdf_mod, "HAS_WEASYPRINT", False)
    with pytest.raises(ImportError, match="pip install codemap\\[pdf\\]"):
        export_pdf(Path("/tmp"), Path("/tmp/out.pdf"))
