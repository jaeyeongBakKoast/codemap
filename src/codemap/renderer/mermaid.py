"""Mermaid diagram renderers for codemap scan results."""

from __future__ import annotations

from codemap.models import (
    ApiSchema,
    DatabaseSchema,
    DependencySchema,
    ScanResult,
)


def render_erd(db: DatabaseSchema) -> str:
    """Generate Mermaid erDiagram syntax from a DatabaseSchema."""
    lines: list[str] = ["erDiagram"]

    # Build a lookup of table foreign keys for relationship rendering
    for table in db.tables:
        table_upper = table.name.upper()

        # Render relationships
        for fk in table.foreignKeys:
            # references format: "other_table.column"
            ref_table = fk.references.split(".")[0].upper()
            lines.append(f"    {table_upper} }}o--|| {ref_table} : \"{fk.column}\"")

        # Render entity with columns
        if table.columns:
            lines.append(f"    {table_upper} {{")
            # Collect FK column names for this table
            fk_columns = {fk.column for fk in table.foreignKeys}
            for col in table.columns:
                markers: list[str] = []
                if col.pk:
                    markers.append("PK")
                if col.name in fk_columns:
                    markers.append("FK")
                marker_str = " " + ",".join(markers) if markers else ""
                lines.append(f"        {col.type} {col.name}{marker_str}")
            lines.append("    }")

    return "\n".join(lines)


def render_sequence(
    api: ApiSchema,
    deps: DependencySchema,
    entries: list[str],
    label: str,
) -> str:
    """Generate Mermaid sequenceDiagram from API and dependency schemas."""
    lines: list[str] = ["sequenceDiagram"]
    lines.append(f"    title {label}")

    # Declare participants in order
    for entry in entries:
        # Use short name (after last dot if present)
        lines.append(f"    participant {entry}")

    entries_set = set(entries)

    for endpoint in api.endpoints:
        controller = endpoint.controller
        service = endpoint.service

        if controller not in entries_set:
            continue

        # Client -> Controller
        lines.append(f"    Client->>+{controller}: {endpoint.method} {endpoint.path}")

        # Controller -> Service
        if service in entries_set:
            lines.append(f"    {controller}->>+{service}: handle()")

            # Service -> each call
            for call in endpoint.calls:
                if call in entries_set:
                    lines.append(f"    {service}->>+{call}: invoke()")
                    lines.append(f"    {call}-->>-{service}: result")

            lines.append(f"    {service}-->>-{controller}: response")

        lines.append(f"    {controller}-->>-Client: response")

    return "\n".join(lines)


def render_architecture(scan: ScanResult) -> str:
    """Generate Mermaid flowchart TD with layered subgraphs."""
    lines: list[str] = ["flowchart TD"]

    # Collect items per layer
    controllers: set[str] = set()
    services: set[str] = set()
    repositories: set[str] = set()
    tables: set[str] = set()
    externals: set[str] = set()

    for endpoint in scan.api.endpoints:
        controllers.add(endpoint.controller)
        if endpoint.service:
            services.add(endpoint.service)
        for call in endpoint.calls:
            # Calls containing "Repository" go to repository layer
            if "Repository" in call or "Repo" in call:
                repositories.add(call)

    for module in scan.dependencies.modules:
        if module.layer == "service":
            services.add(module.name)
        elif module.layer == "repository":
            repositories.add(module.name)
        elif module.layer == "controller":
            controllers.add(module.name)

    for table in scan.database.tables:
        tables.add(table.name.upper())

    for ext in scan.dependencies.externalCalls:
        externals.add(ext.command)

    # Backend subgraph
    backend_items = controllers | services | repositories
    if backend_items:
        lines.append("    subgraph Backend")
        for item in sorted(controllers):
            safe = item.replace(".", "_")
            lines.append(f"        {safe}[{item}]")
        for item in sorted(services):
            safe = item.replace(".", "_")
            lines.append(f"        {safe}[{item}]")
        for item in sorted(repositories):
            safe = item.replace(".", "_")
            lines.append(f"        {safe}[{item}]")
        lines.append("    end")

    # Database subgraph
    if tables:
        lines.append("    subgraph Database")
        for t in sorted(tables):
            lines.append(f"        {t}[({t})]")
        lines.append("    end")

    # External subgraph
    if externals:
        lines.append("    subgraph External")
        for ext in sorted(externals):
            safe = ext.replace(".", "_").replace("-", "_")
            lines.append(f"        {safe}[{ext}]")
        lines.append("    end")

    # Draw edges: controller -> service
    for endpoint in scan.api.endpoints:
        ctrl_safe = endpoint.controller.replace(".", "_")
        svc_safe = endpoint.service.replace(".", "_")
        lines.append(f"    {ctrl_safe} --> {svc_safe}")
        for call in endpoint.calls:
            call_safe = call.replace(".", "_")
            lines.append(f"    {svc_safe} --> {call_safe}")

    # Draw edges: module dependencies
    for module in scan.dependencies.modules:
        src_safe = module.name.replace(".", "_")
        for dep in module.dependsOn:
            dep_safe = dep.replace(".", "_")
            lines.append(f"    {src_safe} --> {dep_safe}")

    return "\n".join(lines)


def render_component(deps: DependencySchema) -> str:
    """Generate Mermaid flowchart TD showing module dependency arrows."""
    lines: list[str] = ["flowchart TD"]

    # Declare all modules as nodes
    all_names: set[str] = set()
    for module in deps.modules:
        all_names.add(module.name)
        for dep in module.dependsOn:
            all_names.add(dep)

    for name in sorted(all_names):
        safe = name.replace(".", "_")
        lines.append(f"    {safe}[{name}]")

    # Draw dependency edges
    for module in deps.modules:
        src_safe = module.name.replace(".", "_")
        for dep in module.dependsOn:
            dep_safe = dep.replace(".", "_")
            lines.append(f"    {src_safe} --> {dep_safe}")

    return "\n".join(lines)
