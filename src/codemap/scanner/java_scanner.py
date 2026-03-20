# src/codemap/scanner/java_scanner.py
from __future__ import annotations

import logging
import re
from pathlib import Path

from codemap.models import Endpoint, Module, Param

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

_PARAM_ANNOTATION_RE = re.compile(
    r"@(RequestParam|RequestBody|PathVariable)"
    r"(?:\(([^)]*)\))?\s+"
    r"(\w+(?:<[^>]+>)?)\s+(\w+)"
)
_REQUIRED_FALSE_RE = re.compile(r"required\s*=\s*false", re.IGNORECASE)


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

        for http_method, method_path, params, return_type in info.get("endpoint_stubs", []):
            full_path = _combine_paths(base_path, method_path)
            endpoints.append(
                Endpoint(
                    method=http_method,
                    path=full_path,
                    controller=cls_name,
                    service=service_name,
                    params=params,
                    returnType=return_type,
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


def _extract_endpoint_stubs(source: str) -> list[tuple[str, str, list[Param], str]]:
    """Extract (http_method, path, params, return_type) tuples from method-level mapping annotations."""
    stubs = []
    lines = source.split("\n")
    for i, line in enumerate(lines):
        match = _METHOD_MAPPING_RE.search(line)
        if not match:
            continue
        http_verb = match.group(1)
        method_path = match.group(2) or ""
        http_method = _HTTP_METHOD_MAP.get(http_verb, http_verb.upper())
        method_sig = _find_method_signature(lines, i)
        params = _extract_method_params(method_sig)
        return_type = _extract_return_type(method_sig)
        stubs.append((http_method, method_path, params, return_type))
    return stubs


def _find_method_signature(lines: list[str], annotation_line: int) -> str:
    sig_parts = []
    # Start from the line after the annotation to skip path-template braces like "/{id}"
    start = annotation_line + 1
    for j in range(start, min(start + 10, len(lines))):
        sig_parts.append(lines[j])
        if "{" in lines[j]:
            break
    return " ".join(sig_parts)


def _extract_method_params(method_sig: str) -> list[Param]:
    params = []
    for m in _PARAM_ANNOTATION_RE.finditer(method_sig):
        annotation = m.group(1)
        annotation_args = m.group(2) or ""
        param_type = m.group(3)
        param_name = m.group(4)
        required = not bool(_REQUIRED_FALSE_RE.search(annotation_args))
        params.append(Param(name=param_name, type=param_type, annotation=annotation, required=required))
    return params


def _extract_return_type(method_sig: str) -> str:
    m = re.search(r"public\s+([\w<>,\s\?]+?)\s+\w+\s*\(", method_sig)
    if m:
        return m.group(1).strip()
    return ""


def _combine_paths(base: str, method: str) -> str:
    """Combine base path and method-level path."""
    base = base.rstrip("/")
    method = method.lstrip("/")
    if not method:
        return base
    return f"{base}/{method}"
