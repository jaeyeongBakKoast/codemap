from __future__ import annotations

import json
import logging
from pathlib import Path

import click

from codemap import __version__
from codemap.config import load_config
from codemap.models import ScanResult


def _load_scan_result(scan_json: Path) -> ScanResult:
    """Load a ScanResult from a JSON file."""
    data = json.loads(scan_json.read_text(encoding="utf-8"))
    return ScanResult(**data)


def _write_output(content: str, output: str | None, quiet: bool = False, label: str = "Output") -> None:
    """Write content to file or stdout."""
    if output:
        out_path = Path(output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(content, encoding="utf-8")
        if not quiet:
            click.echo(f"{label} saved to {output}", err=True)
    else:
        click.echo(content)


@click.group()
@click.version_option(version=__version__)
@click.option("-v", "--verbose", is_flag=True, help="Verbose output")
@click.option("-q", "--quiet", is_flag=True, help="Quiet output")
@click.option("--debug", is_flag=True, help="Debug output")
@click.option("--no-ai", is_flag=True, help="Disable AI enrichment")
@click.pass_context
def main(ctx, verbose, quiet, debug, no_ai):
    ctx.ensure_object(dict)
    level = logging.WARNING
    if verbose:
        level = logging.INFO
    if debug:
        level = logging.DEBUG
    if quiet:
        level = logging.ERROR
    logging.basicConfig(level=level, format="%(levelname)s: %(message)s")
    ctx.obj["verbose"] = verbose
    ctx.obj["quiet"] = quiet
    ctx.obj["no_ai"] = no_ai


def _create_ai_client(ctx, config):
    """Create AiClient if AI is enabled, else return None."""
    if ctx.obj.get("no_ai"):
        return None
    if not config.ai.enabled:
        return None
    if not config.ai.base_url:
        return None
    from codemap.ai.client import AiClient
    return AiClient(config.ai.base_url, config.ai.model, config.ai.language)


@main.command()
@click.argument("path", type=click.Path(exists=True))
@click.option("--target", default="all", help="Scan target: db,api,deps,frontend,all")
@click.option("-o", "--output", type=click.Path(), help="Output JSON file")
@click.pass_context
def scan(ctx, path, target, output):
    """Scan codebase and generate structured JSON."""
    from codemap.scanner import run_scan

    project_path = Path(path)
    config = load_config(project_path)
    targets = set(target.split(","))

    result = run_scan(project_path, config, targets)

    # AI enrichment
    ai_client = _create_ai_client(ctx, config)
    if ai_client:
        from codemap.ai.enrich_scan import enrich_scan
        enrich_scan(result, ai_client)

    json_str = json.dumps(result.model_dump(mode="json", by_alias=True), indent=2, ensure_ascii=False)
    if output:
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).write_text(json_str, encoding="utf-8")
        if not ctx.obj.get("quiet"):
            click.echo(f"Scan result saved to {output}", err=True)
    else:
        click.echo(json_str)


# --- render command ---

_RENDER_TYPES = ["erd", "sequence", "architecture", "component", "all"]


@main.command()
@click.argument("diagram_type", type=click.Choice(_RENDER_TYPES))
@click.option("--from", "from_file", required=True, type=click.Path(exists=True), help="Scan JSON file")
@click.option("--format", "fmt", default="mermaid", type=click.Choice(["mermaid", "drawio"]), help="Output format")
@click.option("-o", "--output", type=click.Path(), help="Output file or directory (for 'all')")
@click.option("--entries", default="", help="Comma-separated entries for sequence diagram")
@click.option("--label", default="", help="Label for sequence diagram")
@click.pass_context
def render(ctx, diagram_type, from_file, fmt, output, entries, label):
    """Render diagrams from scan JSON."""
    scan_result = _load_scan_result(Path(from_file))
    quiet = ctx.obj.get("quiet", False)

    entry_list = [e.strip() for e in entries.split(",") if e.strip()] if entries else []

    if diagram_type == "all":
        out_dir = Path(output) if output else Path(".")
        out_dir.mkdir(parents=True, exist_ok=True)
        ext = ".mmd" if fmt == "mermaid" else ".drawio"
        for dt in ["erd", "sequence", "architecture", "component"]:
            content = _render_single(scan_result, dt, fmt, entry_list, label)
            out_file = out_dir / f"{dt}{ext}"
            out_file.write_text(content, encoding="utf-8")
        if not quiet:
            click.echo(f"Diagrams saved to {out_dir}", err=True)
    else:
        content = _render_single(scan_result, diagram_type, fmt, entry_list, label)
        _write_output(content, output, quiet, "Diagram")


def _render_single(scan: ScanResult, diagram_type: str, fmt: str, entries: list[str], label: str) -> str:
    """Render a single diagram type."""
    if fmt == "mermaid":
        from codemap.renderer.mermaid import render_erd, render_sequence, render_architecture, render_component
        if diagram_type == "erd":
            return render_erd(scan.database)
        elif diagram_type == "sequence":
            return render_sequence(scan.api, scan.dependencies, entries=entries, label=label)
        elif diagram_type == "architecture":
            return render_architecture(scan)
        elif diagram_type == "component":
            return render_component(scan.dependencies)
    else:
        from codemap.renderer.drawio import render_erd_drawio, render_sequence_drawio, render_architecture_drawio, render_component_drawio
        if diagram_type == "erd":
            return render_erd_drawio(scan.database)
        elif diagram_type == "sequence":
            return render_sequence_drawio(scan.api, scan.dependencies, entries=entries, label=label)
        elif diagram_type == "architecture":
            return render_architecture_drawio(scan)
        elif diagram_type == "component":
            return render_component_drawio(scan.dependencies)
    return ""


# --- doc command ---

_DOC_TYPES = ["table-spec", "api-spec", "overview", "all"]


@main.command()
@click.argument("doc_type", type=click.Choice(_DOC_TYPES))
@click.option("--from", "from_file", required=True, type=click.Path(exists=True), help="Scan JSON file")
@click.option("-o", "--output", type=click.Path(), help="Output file or directory (for 'all')")
@click.pass_context
def doc(ctx, doc_type, from_file, output):
    """Generate markdown documents from scan JSON."""
    scan_result = _load_scan_result(Path(from_file))
    quiet = ctx.obj.get("quiet", False)

    ai_client = None
    if not ctx.obj.get("no_ai"):
        config = load_config(Path("."))
        ai_client = _create_ai_client(ctx, config)

    if doc_type == "all":
        out_dir = Path(output) if output else Path(".")
        out_dir.mkdir(parents=True, exist_ok=True)
        for dt in ["table-spec", "api-spec", "overview"]:
            content = _generate_doc(scan_result, dt, ai_client)
            out_file = out_dir / f"{dt}.md"
            out_file.write_text(content, encoding="utf-8")
        if not quiet:
            click.echo(f"Documents saved to {out_dir}", err=True)
    else:
        content = _generate_doc(scan_result, doc_type, ai_client)
        _write_output(content, output, quiet, "Document")


def _generate_doc(scan: ScanResult, doc_type: str, ai_client=None) -> str:
    """Generate a single document type."""
    if doc_type == "table-spec":
        from codemap.doc.table_spec import generate_table_spec
        return generate_table_spec(scan.database, ai_client=ai_client)
    elif doc_type == "api-spec":
        from codemap.doc.api_spec import generate_api_spec
        return generate_api_spec(scan.api, ai_client=ai_client)
    elif doc_type == "overview":
        from codemap.doc.overview import generate_overview
        return generate_overview(scan, ai_client=ai_client)
    return ""


# --- export command ---

@main.command(name="export")
@click.argument("format_type", type=click.Choice(["xlsx", "pdf", "docx"]))
@click.option("--from", "from_file", required=True, type=click.Path(exists=True), help="Scan JSON file or docs directory")
@click.option("--type", "doc_type", default="table-spec", help="Document type for xlsx export")
@click.option("--template", default="minimal", help="Template name for PDF")
@click.option("-o", "--output", required=True, type=click.Path(), help="Output file")
@click.pass_context
def export_cmd(ctx, format_type, from_file, doc_type, template, output):
    """Export to xlsx, pdf, or docx format."""
    from_path = Path(from_file)
    out_path = Path(output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    quiet = ctx.obj.get("quiet", False)

    # Create AI client for auto-chain paths (JSON → doc → export)
    ai_client = None
    if from_path.suffix == ".json" and not ctx.obj.get("no_ai"):
        config = load_config(Path("."))
        ai_client = _create_ai_client(ctx, config)

    if format_type == "xlsx":
        scan_result = _load_scan_result(from_path)
        from codemap.export.xlsx import export_table_spec_xlsx, export_api_spec_xlsx
        if doc_type == "api-spec":
            export_api_spec_xlsx(scan_result, out_path)
        else:
            export_table_spec_xlsx(scan_result, out_path)

    elif format_type == "pdf":
        from codemap.export.pdf import export_pdf
        if from_path.suffix == ".json":
            # Auto-chain: scan JSON → doc → PDF
            scan_result = _load_scan_result(from_path)
            import tempfile
            with tempfile.TemporaryDirectory() as tmp:
                tmp_dir = Path(tmp)
                for dt in ["table-spec", "api-spec", "overview"]:
                    content = _generate_doc(scan_result, dt, ai_client)
                    (tmp_dir / f"{dt}.md").write_text(content, encoding="utf-8")
                css_path = _resolve_template(template)
                export_pdf(tmp_dir, out_path, css_path=css_path)
        else:
            css_path = _resolve_template(template)
            export_pdf(from_path, out_path, css_path=css_path)

    elif format_type == "docx":
        from codemap.export.docx_export import export_docx
        if from_path.suffix == ".json":
            scan_result = _load_scan_result(from_path)
            import tempfile
            with tempfile.TemporaryDirectory() as tmp:
                tmp_dir = Path(tmp)
                for dt in ["table-spec", "api-spec", "overview"]:
                    content = _generate_doc(scan_result, dt, ai_client)
                    (tmp_dir / f"{dt}.md").write_text(content, encoding="utf-8")
                export_docx(tmp_dir, out_path)
        else:
            export_docx(from_path, out_path)

    if not quiet:
        click.echo(f"Exported to {output}", err=True)


def _resolve_template(template_name: str) -> Path | None:
    """Resolve template CSS path. Rejects path separators to prevent traversal."""
    if Path(template_name).name != template_name or any(sep in template_name for sep in ("/", "\\")):
        raise click.BadParameter(f"template must be a simple name without path separators: {template_name}")
    # Project-level
    project_css = Path(".codemap") / "templates" / f"{template_name}.css"
    if project_css.exists():
        return project_css
    # Home-level
    home_css = Path.home() / ".codemap" / "templates" / f"{template_name}.css"
    if home_css.exists():
        return home_css
    return None


# --- generate command ---

@main.command()
@click.argument("path", type=click.Path(exists=True))
@click.option("-o", "--output", required=True, type=click.Path(), help="Output directory")
@click.option("--target", default="all", help="Scan target: db,api,deps,frontend,all")
@click.option("--format", "fmt", default="mermaid", type=click.Choice(["mermaid", "drawio", "all"]))
@click.option("--export", "export_fmt", default="", help="Export format: xlsx,pdf,docx,all")
@click.pass_context
def generate(ctx, path, output, target, fmt, export_fmt):
    """Full pipeline: scan → render → doc → export."""
    from codemap.scanner import run_scan

    project_path = Path(path)
    out_dir = Path(output)
    out_dir.mkdir(parents=True, exist_ok=True)
    quiet = ctx.obj.get("quiet", False)
    config = load_config(project_path)
    targets = set(target.split(","))

    # 1. Scan
    result = run_scan(project_path, config, targets)

    # 1.5 AI enrichment on scan result
    ai_client = _create_ai_client(ctx, config)
    if ai_client:
        from codemap.ai.enrich_scan import enrich_scan
        enrich_scan(result, ai_client)

    scan_file = out_dir / "scan.json"
    json_str = json.dumps(result.model_dump(mode="json", by_alias=True), indent=2, ensure_ascii=False)
    scan_file.write_text(json_str, encoding="utf-8")

    # 2. Render diagrams
    diagram_dir = out_dir / "diagrams"
    diagram_dir.mkdir(exist_ok=True)
    formats = ["mermaid", "drawio"] if fmt == "all" else [fmt]
    for render_fmt in formats:
        ext = ".mmd" if render_fmt == "mermaid" else ".drawio"
        for dt in ["erd", "sequence", "architecture", "component"]:
            content = _render_single(result, dt, render_fmt, [], "")
            (diagram_dir / f"{dt}{ext}").write_text(content, encoding="utf-8")

    # 3. Generate docs (with AI)
    docs_dir = out_dir / "docs"
    docs_dir.mkdir(exist_ok=True)
    for dt in ["table-spec", "api-spec", "overview"]:
        content = _generate_doc(result, dt, ai_client)
        (docs_dir / f"{dt}.md").write_text(content, encoding="utf-8")

    # 4. Export if requested
    if export_fmt:
        export_formats = ["xlsx", "pdf", "docx"] if export_fmt == "all" else export_fmt.split(",")
        export_dir = out_dir / "exports"
        export_dir.mkdir(exist_ok=True)

        for ef in export_formats:
            ef = ef.strip()
            if ef == "xlsx":
                from codemap.export.xlsx import export_table_spec_xlsx, export_api_spec_xlsx
                export_table_spec_xlsx(result, export_dir / "table-spec.xlsx")
                export_api_spec_xlsx(result, export_dir / "api-spec.xlsx")
            elif ef == "pdf":
                try:
                    from codemap.export.pdf import export_pdf
                    css_path = _resolve_template("minimal")
                    export_pdf(docs_dir, export_dir / "report.pdf", css_path=css_path)
                except ImportError:
                    if not quiet:
                        click.echo("PDF export skipped (weasyprint not installed)", err=True)
            elif ef == "docx":
                try:
                    from codemap.export.docx_export import export_docx
                    export_docx(docs_dir, export_dir / "report.docx")
                except ImportError:
                    if not quiet:
                        click.echo("Word export skipped (python-docx not installed)", err=True)

    if not quiet:
        click.echo(f"Generated output in {out_dir}", err=True)
