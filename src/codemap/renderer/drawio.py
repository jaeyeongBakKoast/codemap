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
    node_ids: dict[str, str] = {}  # name -> cell_id for edge drawing

    # Classify items into layers
    controllers: set[str] = set()
    services: set[str] = set()
    repositories: set[str] = set()

    for ep in scan.api.endpoints:
        controllers.add(ep.controller)
        if ep.service:
            services.add(ep.service)
        for call in ep.calls:
            if "Repository" in call or "Repo" in call:
                repositories.add(call)

    for mod in scan.dependencies.modules:
        if mod.layer == "controller":
            controllers.add(mod.name)
        elif mod.layer == "service":
            services.add(mod.name)
        elif mod.layer == "repository":
            repositories.add(mod.name)

    frontend_items = [c.name for c in scan.frontend.components]
    table_items = [t.name for t in scan.database.tables]
    external_items = [ec.command for ec in scan.dependencies.externalCalls]

    layer_defs = [
        ("Frontend", "fillColor=#dae8fc;strokeColor=#6c8ebf;", frontend_items),
        ("Controller", "fillColor=#e1d5e7;strokeColor=#9673a6;", sorted(controllers)),
        ("Service", "fillColor=#d5e8d4;strokeColor=#82b366;", sorted(services)),
        ("Repository", "fillColor=#d5e8d4;strokeColor=#82b366;", sorted(repositories)),
        ("Database", "fillColor=#fff2cc;strokeColor=#d6b656;", table_items),
        ("External", "fillColor=#f8cecc;strokeColor=#b85450;", external_items),
    ]

    y = 20
    for layer_name, style, items in layer_defs:
        if not items:
            continue

        # Layer container
        row_count = (len(items) - 1) // 4 + 1
        layer_height = 40 + row_count * 50
        lid = str(cell_counter)
        cell_counter += 1
        _add_vertex(
            root, lid, layer_name,
            x=20, y=y, width=700, height=layer_height,
            style=f"rounded=1;whiteSpace=wrap;html=1;verticalAlign=top;fontStyle=1;{style}",
        )

        # Items inside the layer
        ix, iy = 30, y + 30
        for item in items:
            iid = str(cell_counter)
            cell_counter += 1
            node_ids[item] = iid
            _add_vertex(
                root, iid, item,
                x=ix, y=iy, width=150, height=30,
                style="rounded=1;whiteSpace=wrap;html=1;fontSize=10;",
            )
            ix += 170
            if ix > 650:
                ix = 30
                iy += 50

        y += layer_height + 20

    # Draw edges: controller → service
    for ep in scan.api.endpoints:
        if ep.controller in node_ids and ep.service and ep.service in node_ids:
            eid = str(cell_counter)
            cell_counter += 1
            _add_edge(root, eid, "", source=node_ids[ep.controller], target=node_ids[ep.service],
                      style="edgeStyle=orthogonalEdgeStyle;")
        # service → calls
        if ep.service and ep.service in node_ids:
            for call in ep.calls:
                if call in node_ids:
                    eid = str(cell_counter)
                    cell_counter += 1
                    _add_edge(root, eid, "", source=node_ids[ep.service], target=node_ids[call],
                              style="edgeStyle=orthogonalEdgeStyle;")

    # Draw edges: module dependencies
    for mod in scan.dependencies.modules:
        if mod.name in node_ids:
            for dep in mod.dependsOn:
                if dep in node_ids:
                    eid = str(cell_counter)
                    cell_counter += 1
                    _add_edge(root, eid, "", source=node_ids[mod.name], target=node_ids[dep],
                              style="edgeStyle=orthogonalEdgeStyle;")

    # Draw edges: external calls (source class → command)
    for ec in scan.dependencies.externalCalls:
        src_class = ec.source.split(".")[0] if ec.source else ""
        if src_class in node_ids and ec.command in node_ids:
            eid = str(cell_counter)
            cell_counter += 1
            _add_edge(root, eid, "", source=node_ids[src_class], target=node_ids[ec.command],
                      style="edgeStyle=orthogonalEdgeStyle;dashed=1;")

    return _to_xml_string(mxfile)


# ---------------------------------------------------------------------------
# Component
# ---------------------------------------------------------------------------

def render_component_drawio(deps: DependencySchema) -> str:
    """Render a Component Diagram in draw.io XML format."""
    mxfile, root = _make_mxfile("Component")

    cell_counter = 2
    module_ids: dict[str, str] = {}

    # Collect all names (modules + their dependencies) to create nodes for all
    all_names: set[str] = set()
    module_types: dict[str, str] = {}
    for mod in deps.modules:
        all_names.add(mod.name)
        module_types[mod.name] = mod.type
        for dep in mod.dependsOn:
            all_names.add(dep)

    x, y = 20, 20
    for name in sorted(all_names):
        mid = str(cell_counter)
        cell_counter += 1
        module_ids[name] = mid

        label = f"{name}\n({module_types[name]})" if name in module_types else name
        style = "rounded=1;whiteSpace=wrap;html=1;"
        if name not in module_types:
            # External dependency - use dashed style
            style = "rounded=1;whiteSpace=wrap;html=1;dashed=1;fillColor=#f5f5f5;"

        _add_vertex(
            root, mid, label,
            x=x, y=y, width=160, height=60,
            style=style,
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
                    root, eid, "",
                    source=module_ids[mod.name],
                    target=module_ids[dep_name],
                    style="edgeStyle=orthogonalEdgeStyle;",
                )

    return _to_xml_string(mxfile)
