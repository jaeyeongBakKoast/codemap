"""Draw.io XML renderer for codemap diagrams."""

from __future__ import annotations

import html
import xml.etree.ElementTree as ET
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

from codemap.models import (
    ApiSchema,
    DatabaseSchema,
    DependencySchema,
    ScanResult,
)


def _make_mxfile(diagram_name: str) -> tuple[ET.Element, ET.Element]:
    """Create the mxfile skeleton and return (mxfile_root, root_cell_parent)."""
    mxfile = ET.Element("mxfile")
    diagram = ET.SubElement(mxfile, "diagram", name=diagram_name)
    graph_model = ET.SubElement(diagram, "mxGraphModel")
    root = ET.SubElement(graph_model, "root")
    ET.SubElement(root, "mxCell", id="0")
    ET.SubElement(root, "mxCell", id="1", parent="0")
    return mxfile, root


def _add_vertex(
    root: ET.Element,
    cell_id: str,
    value: str,
    x: int,
    y: int,
    width: int,
    height: int,
    style: str = "",
    parent: str = "1",
) -> ET.Element:
    cell = ET.SubElement(
        root,
        "mxCell",
        id=cell_id,
        value=html.escape(value),
        style=style,
        vertex="1",
        parent=parent,
    )
    ET.SubElement(cell, "mxGeometry", x=str(x), y=str(y), width=str(width), height=str(height))
    cell.find("mxGeometry").set("as", "geometry")
    return cell


def _add_edge(
    root: ET.Element,
    cell_id: str,
    value: str,
    source: str,
    target: str,
    style: str = "",
    parent: str = "1",
) -> ET.Element:
    cell = ET.SubElement(
        root,
        "mxCell",
        id=cell_id,
        value=html.escape(value),
        style=style,
        edge="1",
        source=source,
        target=target,
        parent=parent,
    )
    geo = ET.SubElement(cell, "mxGeometry", relative="1")
    geo.set("as", "geometry")
    return cell


def _to_xml_string(mxfile: ET.Element) -> str:
    return ET.tostring(mxfile, encoding="unicode", xml_declaration=False)


# ---------------------------------------------------------------------------
# ERD
# ---------------------------------------------------------------------------

def render_erd_drawio(db: DatabaseSchema) -> str:
    """Render an Entity-Relationship Diagram in draw.io XML format."""
    mxfile, root = _make_mxfile("ERD")

    table_ids: dict[str, str] = {}
    x_offset = 20
    cell_counter = 2

    for table in db.tables:
        tid = str(cell_counter)
        cell_counter += 1
        table_ids[table.name] = tid

        # Build label with columns
        lines = [f"<b>{html.escape(table.name)}</b>"]
        for col in table.columns:
            pk_marker = " [PK]" if col.pk else ""
            lines.append(f"{html.escape(col.name)}: {html.escape(col.type)}{pk_marker}")
        label = "<br/>".join(lines)

        _add_vertex(
            root,
            tid,
            "",
            x=x_offset,
            y=20,
            width=200,
            height=30 + 20 * len(table.columns),
            style="rounded=1;whiteSpace=wrap;html=1;",
        )
        # Set value directly (already contains html-escaped content via our lines)
        root.find(f".//mxCell[@id='{tid}']").set("value", label)

        x_offset += 260

    # FK edges
    for table in db.tables:
        for fk in table.foreignKeys:
            ref_table = fk.references.split(".")[0]
            if ref_table in table_ids and table.name in table_ids:
                eid = str(cell_counter)
                cell_counter += 1
                _add_edge(
                    root,
                    eid,
                    fk.column,
                    source=table_ids[table.name],
                    target=table_ids[ref_table],
                    style="edgeStyle=orthogonalEdgeStyle;",
                )

    return _to_xml_string(mxfile)


# ---------------------------------------------------------------------------
# Sequence
# ---------------------------------------------------------------------------

def render_sequence_drawio(
    api: ApiSchema,
    deps: DependencySchema,
    entries: list[str],
    label: str,
) -> str:
    """Render a Sequence Diagram in draw.io XML format."""
    mxfile, root = _make_mxfile(html.escape(label))

    cell_counter = 2
    participant_ids: dict[str, str] = {}

    # Participants (vertical lifelines)
    x = 40
    for entry in entries:
        pid = str(cell_counter)
        cell_counter += 1
        participant_ids[entry] = pid

        _add_vertex(
            root,
            pid,
            entry,
            x=x,
            y=20,
            width=140,
            height=40,
            style="rounded=1;whiteSpace=wrap;html=1;",
        )

        # Lifeline
        lid = str(cell_counter)
        cell_counter += 1
        _add_vertex(
            root,
            lid,
            "",
            x=x + 68,
            y=60,
            width=4,
            height=300,
            style="line;strokeDashGap=4;html=1;",
        )

        x += 200

    # Messages from endpoints
    y_msg = 100
    for ep in api.endpoints:
        chain = [ep.controller, ep.service, *ep.calls]
        for i in range(len(chain) - 1):
            src_name = chain[i]
            tgt_name = chain[i + 1]
            if src_name in participant_ids and tgt_name in participant_ids:
                eid = str(cell_counter)
                cell_counter += 1
                _add_edge(
                    root,
                    eid,
                    f"{ep.method} {ep.path}",
                    source=participant_ids[src_name],
                    target=participant_ids[tgt_name],
                    style="edgeStyle=orthogonalEdgeStyle;html=1;",
                )
                y_msg += 40

    return _to_xml_string(mxfile)


# ---------------------------------------------------------------------------
# Architecture
# ---------------------------------------------------------------------------

def render_architecture_drawio(scan: ScanResult) -> str:
    """Render a layered Architecture Diagram in draw.io XML format."""
    mxfile, root = _make_mxfile("Architecture")

    cell_counter = 2
    layers = [
        ("Frontend", "fillColor=#dae8fc;strokeColor=#6c8ebf;"),
        ("Backend", "fillColor=#d5e8d4;strokeColor=#82b366;"),
        ("Database", "fillColor=#fff2cc;strokeColor=#d6b656;"),
        ("External", "fillColor=#f8cecc;strokeColor=#b85450;"),
    ]

    y = 20
    for layer_name, style in layers:
        lid = str(cell_counter)
        cell_counter += 1
        _add_vertex(
            root,
            lid,
            layer_name,
            x=20,
            y=y,
            width=600,
            height=80,
            style=f"rounded=1;whiteSpace=wrap;html=1;{style}",
        )

        # Populate with items
        items: list[str] = []
        if layer_name == "Backend" and scan.api:
            for ep in scan.api.endpoints:
                items.append(f"{ep.method} {ep.path}")
        elif layer_name == "Database" and scan.database:
            for t in scan.database.tables:
                items.append(t.name)
        elif layer_name == "Frontend" and scan.frontend:
            for c in scan.frontend.components:
                items.append(c.name)
        elif layer_name == "External" and scan.dependencies:
            for ec in scan.dependencies.externalCalls:
                items.append(ec.command)

        if items:
            ix = 30
            for item in items:
                iid = str(cell_counter)
                cell_counter += 1
                _add_vertex(
                    root,
                    iid,
                    item,
                    x=ix,
                    y=y + 30,
                    width=140,
                    height=30,
                    style="rounded=1;whiteSpace=wrap;html=1;fontSize=10;",
                )
                ix += 160

        y += 120

    return _to_xml_string(mxfile)


# ---------------------------------------------------------------------------
# Component
# ---------------------------------------------------------------------------

def render_component_drawio(deps: DependencySchema) -> str:
    """Render a Component Diagram in draw.io XML format."""
    mxfile, root = _make_mxfile("Component")

    cell_counter = 2
    module_ids: dict[str, str] = {}

    x, y = 20, 20
    for mod in deps.modules:
        mid = str(cell_counter)
        cell_counter += 1
        module_ids[mod.name] = mid

        _add_vertex(
            root,
            mid,
            f"{mod.name}\n({mod.type})",
            x=x,
            y=y,
            width=160,
            height=60,
            style="rounded=1;whiteSpace=wrap;html=1;",
        )
        x += 220
        if x > 600:
            x = 20
            y += 100

    # Dependency edges
    for mod in deps.modules:
        for dep_name in mod.dependsOn:
            if mod.name in module_ids and dep_name in module_ids:
                eid = str(cell_counter)
                cell_counter += 1
                _add_edge(
                    root,
                    eid,
                    "",
                    source=module_ids[mod.name],
                    target=module_ids[dep_name],
                    style="edgeStyle=orthogonalEdgeStyle;",
                )

    return _to_xml_string(mxfile)
