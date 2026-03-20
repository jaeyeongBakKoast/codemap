# src/codemap/scanner/ts_scanner.py
from __future__ import annotations

import logging
import re
from pathlib import Path

from codemap.models import Component, ApiCall

logger = logging.getLogger(__name__)

# Component declaration patterns
_EXPORT_COMPONENT_RE = re.compile(
    r"export\s+(?:const|function)\s+(\w+)"
)

# Hook call pattern: useState, useEffect, useCallback, useMemo, useRef, etc.
_HOOK_CALL_RE = re.compile(r"\b(use[A-Z]\w*)\s*\(")

# Import patterns for child component detection
_IMPORT_COMPONENT_RE = re.compile(
    r"import\s+(?:\{[^}]*\b(\w+)\b[^}]*\}|(\w+))\s+from\s+['\"]\./"
)

# JSX component usage: <ComponentName or <ComponentName>
_JSX_COMPONENT_RE = re.compile(r"<([A-Z]\w+)[\s/>]")

# axios API call patterns
_AXIOS_CALL_RE = re.compile(
    r"axios\.(get|post|put|delete|patch)\s*\(\s*['\"`]([^'\"`]+)['\"`]"
)

# fetch() API call patterns
_FETCH_CALL_RE = re.compile(
    r"fetch\s*\(\s*['\"`]([^'\"`]+)['\"`](?:\s*,\s*\{[^}]*method\s*:\s*['\"](\w+)['\"])?"
)


def scan_typescript(
    ts_files: list[Path],
) -> tuple[list[Component], list[ApiCall]]:
    """Parse TypeScript/React files and extract components and API calls."""
    if not ts_files:
        return [], []

    components: list[Component] = []
    api_calls: list[ApiCall] = []

    for ts_file in ts_files:
        try:
            source = ts_file.read_text(encoding="utf-8")
        except Exception as e:
            logger.warning(f"Failed to read {ts_file}: {e}")
            continue

        file_components, file_api_calls = _parse_ts_file(source, ts_file)
        components.extend(file_components)
        api_calls.extend(file_api_calls)

    return components, api_calls


def _parse_ts_file(
    source: str, file_path: Path
) -> tuple[list[Component], list[ApiCall]]:
    """Extract component metadata from a single TS/TSX file."""
    components: list[Component] = []
    api_calls: list[ApiCall] = []

    # Find exported component names
    comp_names = [m.group(1) for m in _EXPORT_COMPONENT_RE.finditer(source)]
    if not comp_names:
        return components, api_calls

    # Collect imported component names from relative imports
    imported_components: set[str] = set()
    for m in _IMPORT_COMPONENT_RE.finditer(source):
        name = m.group(1) or m.group(2)
        if name and name[0].isupper():
            imported_components.add(name)

    # Find JSX component usages (uppercase = component)
    jsx_usages: set[str] = set()
    for m in _JSX_COMPONENT_RE.finditer(source):
        jsx_usages.add(m.group(1))

    # Children = imported components that are also used in JSX
    children = sorted(imported_components & jsx_usages)

    # Find hooks
    hooks = sorted({m.group(1) for m in _HOOK_CALL_RE.finditer(source)})

    # Build component entries
    for comp_name in comp_names:
        components.append(
            Component(
                name=comp_name,
                file=str(file_path.name),
                children=children,
                hooks=hooks,
            )
        )

    # Find API calls
    for line_no, line in enumerate(source.splitlines(), start=1):
        for m in _AXIOS_CALL_RE.finditer(line):
            method = m.group(1).upper()
            path = m.group(2)
            api_calls.append(
                ApiCall(
                    component=comp_names[0] if comp_names else "",
                    method=method,
                    path=path,
                    file=str(file_path.name),
                    line=line_no,
                )
            )
        for m in _FETCH_CALL_RE.finditer(line):
            path = m.group(1)
            method = (m.group(2) or "GET").upper()
            api_calls.append(
                ApiCall(
                    component=comp_names[0] if comp_names else "",
                    method=method,
                    path=path,
                    file=str(file_path.name),
                    line=line_no,
                )
            )

    return components, api_calls
