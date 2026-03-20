from __future__ import annotations

from pathlib import Path

try:
    import weasyprint
    HAS_WEASYPRINT = True
except ImportError:
    HAS_WEASYPRINT = False

import markdown


def export_pdf(docs_dir: Path, output: Path, css_path: Path | None = None) -> None:
    """Export markdown files from docs_dir to a single PDF."""
    if not HAS_WEASYPRINT:
        raise ImportError(
            "weasyprint is required for PDF export. "
            "Install with: pip install codemap[pdf]"
        )

    # Collect and sort markdown files
    md_files = sorted(docs_dir.glob("*.md"))
    if not md_files:
        # Create a minimal PDF with a message
        html_content = "<html><body><p>No documents found.</p></body></html>"
    else:
        parts = []
        for md_file in md_files:
            md_text = md_file.read_text(encoding="utf-8")
            html_part = markdown.markdown(md_text, extensions=["tables", "fenced_code"])
            parts.append(html_part)
        html_body = "\n<hr/>\n".join(parts)

        css_content = ""
        if css_path and css_path.exists():
            css_content = f"<style>{css_path.read_text(encoding='utf-8')}</style>"

        html_content = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
{css_content}
<style>
body {{ font-family: sans-serif; margin: 2cm; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
th {{ background-color: #4472C4; color: white; }}
</style>
</head>
<body>
{html_body}
</body>
</html>"""

    html = weasyprint.HTML(string=html_content)
    html.write_pdf(str(output))
