# src/codemap/scanner/java_scanner.py
from __future__ import annotations

import logging
import re
from pathlib import Path

from codemap.models import Endpoint, Module

logger = logging.getLogger(__name__)

# Annotation patterns
_CLASS_ANNOTATION_RE = re.compile(
    r"@(RestController|Controller|Service|Repository|Component)\b"
)
_REQUEST_MAPPING_RE = re.compile(
    r'@RequestMapping\(\s*(?:value\s*=\s*)?["\']([^"\']+)["\']'
)
_METHOD_MAPPING_RE = re.compile(
    r'@(Get|Post|Put|Delete|Patch)Mapping(?:\(\s*(?:value\s*=\s*)?["\']([^"\']*)["\'])?'
)
_CLASS_NAME_RE = re.compile(r"\bclass\s+(\w+)")
# Match constructor parameters: TypeName varName (,|))
_CONSTRUCTOR_PARAM_RE = re.compile(r"\b([A-Z]\w+)\s+\w+\s*(?:,|\))")


_LAYER_MAP = {
    "RestController": "controller",
    "Controller": "controller",
    "Service": "service",
    "Repository": "repository",
    "Component": "component",
}

_HTTP_METHOD_MAP = {
    "Get": "GET",
    "Post": "POST",
    "Put": "PUT",
    "Delete": "DELETE",
    "Patch": "PATCH",
}


def scan_java(java_files: list[Path]) -> tuple[list[Endpoint], list[Module]]:
    """Parse Spring Boot Java files and extract endpoints and modules."""
    if not java_files:
        return [], []

    # First pass: collect class info from all files
    class_info: dict[str, dict] = {}  # class_name -> {layer, deps, endpoints_raw, file}

    for java_file in java_files:
        try:
            source = java_file.read_text(encoding="utf-8")
        except Exception as e:
            logger.warning(f"Failed to read {java_file}: {e}")
            continue

        info = _parse_java_file(source, java_file)
        if info:
            class_info[info["name"]] = info

    # Build modules
    modules: list[Module] = []
    for cls_name, info in class_info.items():
        modules.append(
            Module(
                name=cls_name,
                type="class",
                file=str(info["file"]),
                dependsOn=info["deps"],
                layer=info["layer"],
            )
        )

    # Build endpoints from controller classes
    endpoints: list[Endpoint] = []
    for cls_name, info in class_info.items():
        if info["layer"] != "controller":
            continue

        # Determine service name: first injected dependency that is a known service
        # or first dependency that ends with "Service"
        service_name = ""
        for dep in info["deps"]:
            if dep in class_info and class_info[dep]["layer"] == "service":
                service_name = dep
                break
        if not service_name:
            for dep in info["deps"]:
                if dep.endswith("Service"):
                    service_name = dep
                    break

        base_path = info.get("base_path", "")

        for http_method, method_path in info.get("endpoint_stubs", []):
            full_path = _combine_paths(base_path, method_path)
            endpoints.append(
                Endpoint(
                    method=http_method,
                    path=full_path,
                    controller=cls_name,
                    service=service_name,
                )
            )

    return endpoints, modules


def _parse_java_file(source: str, file_path: Path) -> dict | None:
    """Extract class metadata from a single Java source file."""
    # Find class annotations
    class_annotation_match = _CLASS_ANNOTATION_RE.search(source)
    if not class_annotation_match:
        return None

    annotation_name = class_annotation_match.group(1)
    layer = _LAYER_MAP.get(annotation_name, "component")

    # Find class name
    class_name_match = _CLASS_NAME_RE.search(source)
    if not class_name_match:
        return None
    class_name = class_name_match.group(1)

    # Find constructor and extract parameter types as dependencies
    deps = _extract_constructor_deps(source, class_name)

    # Base path from @RequestMapping on class
    base_path = ""
    req_mapping_match = _REQUEST_MAPPING_RE.search(source)
    if req_mapping_match:
        base_path = req_mapping_match.group(1)

    # Extract endpoint stubs for controllers
    endpoint_stubs = []
    if layer == "controller":
        endpoint_stubs = _extract_endpoint_stubs(source)

    return {
        "name": class_name,
        "layer": layer,
        "file": file_path,
        "deps": deps,
        "base_path": base_path,
        "endpoint_stubs": endpoint_stubs,
    }


def _extract_constructor_deps(source: str, class_name: str) -> list[str]:
    """Extract injected dependency type names from the constructor."""
    # Match constructor: public ClassName(...)
    constructor_re = re.compile(
        r"public\s+" + re.escape(class_name) + r"\s*\(([^)]*)\)"
    )
    match = constructor_re.search(source)
    if not match:
        return []

    params_str = match.group(1).strip()
    if not params_str:
        return []

    deps: list[str] = []
    # Each parameter is: [annotations] TypeName varName
    # Split by comma, strip annotations
    for param in params_str.split(","):
        param = param.strip()
        # Remove annotation tokens like @RequestBody
        param = re.sub(r"@\w+\s*", "", param).strip()
        # Type is first token, name is second
        tokens = param.split()
        if len(tokens) >= 2:
            type_name = tokens[0]
            # Only include if it looks like a class name (uppercase first letter)
            if type_name and type_name[0].isupper():
                deps.append(type_name)

    return deps


def _extract_endpoint_stubs(source: str) -> list[tuple[str, str]]:
    """Extract (http_method, path) pairs from method-level mapping annotations."""
    stubs = []
    for match in _METHOD_MAPPING_RE.finditer(source):
        http_verb = match.group(1)
        method_path = match.group(2) or ""
        http_method = _HTTP_METHOD_MAP.get(http_verb, http_verb.upper())
        stubs.append((http_method, method_path))
    return stubs


def _combine_paths(base: str, method: str) -> str:
    """Combine base path and method-level path."""
    base = base.rstrip("/")
    method = method.lstrip("/")
    if not method:
        return base
    return f"{base}/{method}"
