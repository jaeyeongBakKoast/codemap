# src/codemap/scanner/java_scanner.py
from __future__ import annotations

import logging
import re
from pathlib import Path

from codemap.models import Endpoint, Module, Param, JavaField

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

_FIELD_RE = re.compile(r"private\s+(?:final\s+)?([\w<>,\s\?]+?)\s+(\w+)\s*;")
_LINE_COMMENT_RE = re.compile(r"^\s*//\s*(.+)$")


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


def scan_java(java_files: list[Path]) -> tuple[list[Endpoint], list[Module], dict[str, list[JavaField]]]:
    """Parse Spring Boot Java files and extract endpoints, modules, and class fields."""
    if not java_files:
        return [], [], {}

    # First pass: collect class info from all files
    class_info: dict[str, dict] = {}  # class_name -> {layer, deps, endpoints_raw, file}
    class_fields: dict[str, list[JavaField]] = {}

    for java_file in java_files:
        try:
            source = java_file.read_text(encoding="utf-8")
        except Exception as e:
            logger.warning(f"Failed to read {java_file}: {e}")
            continue

        info = _parse_java_file(source, java_file)
        if info:
            class_info[info["name"]] = info

        # Parse ALL class fields
        class_name_match = _CLASS_NAME_RE.search(source)
        if class_name_match:
            cls_name = class_name_match.group(1)
            fields = _parse_class_fields(source)
            if fields:
                class_fields[cls_name] = fields

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

    # Resolve request/response fields from class_fields
    for ep in endpoints:
        ep.requestFields = _resolve_request_fields(ep, class_fields)
        ep.responseFields = _resolve_response_fields(ep, class_fields)

    return endpoints, modules, class_fields


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
    # First, collect annotated params
    annotated_names: set[str] = set()
    for m in _PARAM_ANNOTATION_RE.finditer(method_sig):
        annotation = m.group(1)
        annotation_args = m.group(2) or ""
        param_type = m.group(3)
        param_name = m.group(4)
        required = not bool(_REQUIRED_FALSE_RE.search(annotation_args))
        params.append(Param(name=param_name, type=param_type, annotation=annotation, required=required))
        annotated_names.add(param_name)

    # Then, find unannotated params (Spring implicit query binding)
    # Extract the content inside the method parentheses
    paren_match = re.search(r"\(([^)]*)\)", method_sig)
    if paren_match:
        params_str = paren_match.group(1)
        # Split by comma, process each parameter
        for part in params_str.split(","):
            part = part.strip()
            if not part:
                continue
            # Skip if it has a known annotation
            if re.search(r"@(RequestParam|RequestBody|PathVariable|PageableDefault|AuthenticationPrincipal|ModelAttribute)", part):
                continue
            # Skip framework types: Pageable, HttpServletRequest, HttpServletResponse, etc.
            if re.search(r"\b(Pageable|HttpServlet|Principal|BindingResult|Model|RedirectAttributes|MultipartFile)\b", part):
                continue
            # Remove any remaining annotations
            cleaned = re.sub(r"@\w+(?:\([^)]*\))?\s*", "", part).strip()
            tokens = cleaned.split()
            if len(tokens) >= 2:
                param_type = tokens[-2]
                param_name = tokens[-1]
                if param_name not in annotated_names and param_type[0].isupper():
                    params.append(Param(name=param_name, type=param_type, annotation="QueryParam", required=False))

    return params


def _extract_return_type(method_sig: str) -> str:
    m = re.search(r"public\s+([\w<>,\s\?]+?)\s+\w+\s*\(", method_sig)
    if m:
        return m.group(1).strip()
    return ""


def _parse_class_fields(source: str) -> list[JavaField]:
    """Extract field declarations (private [final] Type name;) with preceding line comments."""
    fields: list[JavaField] = []
    lines = source.split("\n")
    for i, line in enumerate(lines):
        m = _FIELD_RE.search(line)
        if not m:
            continue
        field_type = m.group(1).strip()
        field_name = m.group(2)
        comment = ""
        if i > 0:
            cm = _LINE_COMMENT_RE.match(lines[i - 1])
            if cm:
                comment = cm.group(1).strip()
        if not comment:
            comment = _auto_describe(field_name)
        fields.append(JavaField(name=field_name, type=field_type, comment=comment))
    return fields


# Common Java field name fragments → Korean descriptions
_FIELD_NAME_KO: dict[str, str] = {
    "id": "고유번호",
    "name": "이름",
    "email": "이메일",
    "password": "비밀번호",
    "phone": "전화번호",
    "address": "주소",
    "status": "상태",
    "type": "유형",
    "code": "코드",
    "title": "제목",
    "content": "내용",
    "description": "설명",
    "comment": "비고",
    "remarks": "비고",
    "path": "경로",
    "url": "URL",
    "key": "키",
    "value": "값",
    "count": "건수",
    "total": "합계",
    "amount": "금액",
    "price": "가격",
    "quantity": "수량",
    "order": "순서",
    "sort": "정렬",
    "index": "인덱스",
    "level": "레벨",
    "depth": "깊이",
    "size": "크기",
    "width": "너비",
    "height": "높이",
    "length": "길이",
    "weight": "무게",
    "lat": "위도",
    "latitude": "위도",
    "lng": "경도",
    "lon": "경도",
    "longitude": "경도",
    "date": "일시",
    "time": "시간",
    "year": "연도",
    "month": "월",
    "day": "일",
    "hour": "시",
    "minute": "분",
    "second": "초",
    "created": "생성",
    "updated": "수정",
    "modified": "수정",
    "deleted": "삭제",
    "start": "시작",
    "end": "종료",
    "begin": "시작",
    "finish": "종료",
    "active": "활성",
    "enabled": "활성",
    "disabled": "비활성",
    "visible": "표시",
    "hidden": "숨김",
    "flag": "플래그",
    "result": "결과",
    "message": "메시지",
    "error": "오류",
    "version": "버전",
    "port": "항구",
    "username": "사용자명",
    "user": "사용자",
    "role": "역할",
    "group": "그룹",
    "parent": "부모",
    "children": "자식",
    "ancestor": "조상",
    "file": "파일",
    "image": "이미지",
    "video": "영상",
    "vessel": "선박",
    "device": "장비",
    "camera": "카메라",
    "sensor": "센서",
    "project": "프로젝트",
    "session": "세션",
    "token": "토큰",
    "login": "로그인",
    "last": "최근",
    "full": "전체",
    "is": "",
    "has": "",
    "can": "",
}


def _split_camel(name: str) -> list[str]:
    """Split camelCase into lowercase words: 'createdAt' -> ['created', 'at']."""
    parts = re.sub(r"([a-z])([A-Z])", r"\1_\2", name).lower().split("_")
    return [p for p in parts if p]


def _auto_describe(field_name: str) -> str:
    """Generate Korean description from camelCase field name."""
    words = _split_camel(field_name)
    translated = []
    for w in words:
        ko = _FIELD_NAME_KO.get(w, "")
        if ko:
            translated.append(ko)

            
    return " ".join(translated) if translated else ""


_COLLECTION_TYPES = {"List", "Set", "Collection"}
_FRAMEWORK_WRAPPERS = {"ResponseEntity", "ApiResponse"}


def _extract_generic_parts(type_str: str) -> tuple[str, str]:
    """Extract outer type and inner type from a generic: 'Foo<Bar>' -> ('Foo', 'Bar')."""
    m = re.match(r"(\w+)<(.+)>$", type_str.strip())
    if m:
        return m.group(1), m.group(2).strip()
    return type_str, ""


def _resolve_request_fields(ep: Endpoint, class_fields: dict[str, list[JavaField]]) -> list[JavaField]:
    """Resolve @RequestBody parameter type to its class fields."""
    for p in ep.params:
        if p.annotation == "RequestBody" and p.type in class_fields:
            return class_fields[p.type]
    return []


def _resolve_response_fields(ep: Endpoint, class_fields: dict[str, list[JavaField]]) -> list[JavaField]:
    """Resolve return type to its class fields by unwrapping generics.

    For generic wrappers like ResultResponse<CampaignResponse>:
    - If the outer type has fields in class_fields, include them (wrapper fields)
    - Unwrap collections (List, Set) and framework wrappers (ResponseEntity)
    - If the inner type has fields in class_fields, include them too
    - Result: wrapper fields + inner type fields combined
    """
    if not ep.returnType:
        return []

    result_fields: list[JavaField] = []
    type_str = ep.returnType

    # Peel layers, collecting fields from known wrapper types
    changed = True
    while changed:
        changed = False
        outer, inner = _extract_generic_parts(type_str)

        if not inner:
            break

        # Skip framework wrappers (ResponseEntity) — no useful fields
        if outer in _FRAMEWORK_WRAPPERS:
            type_str = inner
            changed = True
            continue

        # Skip collection types (List, Set, Collection)
        if outer in _COLLECTION_TYPES:
            type_str = inner
            changed = True
            continue

        # If outer type has fields in class_fields, it's a domain wrapper
        if outer in class_fields:
            result_fields.extend(class_fields[outer])
            type_str = inner
            changed = True
            continue

        # Unknown wrapper — stop unwrapping
        break

    # Unwrap any remaining collections
    changed = True
    while changed:
        changed = False
        outer, inner = _extract_generic_parts(type_str)
        if outer in _COLLECTION_TYPES and inner:
            type_str = inner
            changed = True

    # Add inner type fields
    if type_str in class_fields:
        result_fields.extend(class_fields[type_str])

    return result_fields


def _combine_paths(base: str, method: str) -> str:
    """Combine base path and method-level path."""
    base = base.rstrip("/")
    method = method.lstrip("/")
    if not method:
        return base
    return f"{base}/{method}"
