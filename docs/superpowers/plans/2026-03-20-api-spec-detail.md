# API 명세서 상세화: Java Entity/DTO 필드 파싱 + 엔드포인트별 확장 출력

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Java Entity/DTO 클래스의 필드를 파싱하고, 엔드포인트의 `@RequestBody` 타입과 반환 타입(`ApiResponse<T>`)에서 `T`를 해석하여 필드를 풀어서, API 명세서에 엔드포인트별 입력/응답 필드 테이블로 출력한다.

**Architecture:** (1) Java 클래스 필드 파서를 추가하여 `private Type name; // comment` 패턴을 추출, (2) scan_java에서 모든 클래스(Entity/DTO 포함)의 필드를 수집하여 `classFields` dict에 저장, (3) Endpoint에 입력/응답 필드 정보를 `requestFields`/`responseFields`로 resolve하여 저장, (4) api_spec.py에서 엔드포인트별 섹션으로 출력.

**Tech Stack:** Python 3.12, regex, Pydantic

**Reference:** iuu 프로젝트의 Entity/DTO 클래스 패턴:
```java
// 한국어 주석
private String fieldName;
```

---

## File Structure

```
src/codemap/
├── models.py                          # JavaField 모델 추가, Endpoint에 requestFields/responseFields 추가, ApiSchema에 classFields 추가
├── scanner/
│   └── java_scanner.py                # _parse_class_fields() 추가, scan_java()에서 타입 해석 로직 추가
├── doc/
│   └── api_spec.py                    # 엔드포인트별 섹션 출력으로 전면 재작성
└── export/
    └── xlsx.py                        # API 시트를 엔드포인트별 시트로 재구성
tests/
├── fixtures/
│   ├── UserController.java            # 기존 (변경 없음)
│   ├── UserService.java               # 기존 (변경 없음)
│   ├── User.java                      # NEW: Entity fixture (fields + comments)
│   └── UserRequest.java               # NEW: DTO fixture
├── scanner/
│   └── test_java_scanner.py           # classFields, requestFields/responseFields 테스트 추가
├── doc/
│   └── test_api_spec.py               # 상세 출력 테스트 추가
└── export/
    └── test_xlsx.py                   # 상세 API 시트 테스트 추가
```

---

## Task 1: 모델 확장 — JavaField, requestFields, responseFields

**Files:**
- Modify: `src/codemap/models.py`
- Modify: `tests/test_models.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_models.py — import에 JavaField 추가
# from codemap.models import (...기존..., JavaField)

def test_java_field():
    field = JavaField(name="deviceId", type="Integer", comment="고유번호")
    assert field.name == "deviceId"
    assert field.type == "Integer"
    assert field.comment == "고유번호"


def test_java_field_default_comment():
    field = JavaField(name="id", type="Long")
    assert field.comment == ""


def test_endpoint_request_fields():
    ep = Endpoint(
        method="POST", path="/api/users", controller="C", service="S",
        requestFields=[
            JavaField(name="email", type="String", comment="이메일"),
        ],
    )
    assert len(ep.requestFields) == 1
    assert ep.requestFields[0].comment == "이메일"


def test_endpoint_response_fields():
    ep = Endpoint(
        method="GET", path="/api/users", controller="C", service="S",
        responseFields=[
            JavaField(name="deviceId", type="Integer", comment="고유번호"),
            JavaField(name="deviceName", type="String", comment="장비명"),
        ],
    )
    assert len(ep.responseFields) == 2


def test_endpoint_fields_default():
    ep = Endpoint(method="GET", path="/api/test", controller="C", service="S")
    assert ep.requestFields == []
    assert ep.responseFields == []


def test_api_schema_class_fields():
    schema = ApiSchema(
        classFields={"User": [JavaField(name="id", type="Long", comment="고유번호")]},
    )
    assert "User" in schema.classFields
    assert schema.classFields["User"][0].name == "id"


def test_api_schema_class_fields_default():
    schema = ApiSchema()
    assert schema.classFields == {}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_models.py::test_java_field -v`
Expected: FAIL

- [ ] **Step 3: Implement model changes**

```python
# src/codemap/models.py — 추가/수정

class JavaField(BaseModel):
    """Java 클래스의 필드 정보 (Entity/DTO 멤버 변수)"""
    name: str
    type: str
    comment: str = ""


# Endpoint에 추가:
class Endpoint(BaseModel):
    method: str
    path: str
    controller: str
    service: str
    calls: list[str] = Field(default_factory=list)
    params: list[Param] = Field(default_factory=list)
    returnType: str = ""
    requestFields: list[JavaField] = Field(default_factory=list)     # NEW
    responseFields: list[JavaField] = Field(default_factory=list)    # NEW


# ApiSchema에 추가:
class ApiSchema(BaseModel):
    endpoints: list[Endpoint] = Field(default_factory=list)
    classFields: dict[str, list[JavaField]] = Field(default_factory=dict)  # NEW: className -> fields
```

`JavaField` 클래스는 `Param` 뒤, `Endpoint` 앞에 배치한다.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_models.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/codemap/models.py tests/test_models.py
git commit -m "feat: add JavaField model and requestFields/responseFields to Endpoint"
```

---

## Task 2: Java 클래스 필드 파싱 + 타입 해석

**Files:**
- Modify: `src/codemap/scanner/java_scanner.py`
- Create: `tests/fixtures/User.java`
- Create: `tests/fixtures/UserRequest.java`
- Modify: `tests/scanner/test_java_scanner.py`

- [ ] **Step 1: Create Java Entity fixture**

```java
// tests/fixtures/User.java
package com.example.user;

import lombok.*;
import java.time.LocalDateTime;

@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
public class User {

    // 사용자 고유번호
    private Long id;
    // 이메일 주소
    private String email;
    // 사용자명
    private String name;
    // 소속 부서 ID
    private Long deptId;
    // 등록일
    private LocalDateTime createdAt;
}
```

- [ ] **Step 2: Create Java DTO fixture**

```java
// tests/fixtures/UserRequest.java
package com.example.user;

import lombok.*;

@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
public class UserRequest {

    // 이메일 주소
    private String email;
    // 사용자명
    private String name;
}
```

- [ ] **Step 3: Update ALL existing test unpacking sites (CRITICAL)**

`scan_java()` 반환값이 2-tuple에서 3-tuple로 바뀌므로, `tests/scanner/test_java_scanner.py`의 **모든** 기존 호출을 수정해야 함:

```python
# 기존: endpoints, modules = scan_java(...)  →  endpoints, modules, _ = scan_java(...)
# 기존: endpoints, _ = scan_java(...)        →  endpoints, _, _ = scan_java(...)
# 기존: _, modules = scan_java(...)          →  _, modules, _ = scan_java(...)

# test_scan_java_empty도 수정:
def test_scan_java_empty():
    endpoints, modules, class_fields = scan_java([])
    assert endpoints == []
    assert modules == []
    assert class_fields == {}
```

파일 내 모든 `scan_java(` 호출을 찾아서 3-tuple 언패킹으로 일괄 수정한다.

- [ ] **Step 4: Write new failing tests**

```python
# tests/scanner/test_java_scanner.py 에 추가

def test_scan_java_class_fields():
    """Entity/DTO 클래스의 필드와 주석을 파싱"""
    endpoints, modules, class_fields = scan_java(
        [FIXTURE_DIR / "User.java"]
    )
    assert "User" in class_fields
    fields = class_fields["User"]
    assert len(fields) == 5
    id_field = next(f for f in fields if f.name == "id")
    assert id_field.type == "Long"
    assert id_field.comment == "사용자 고유번호"
    email_field = next(f for f in fields if f.name == "email")
    assert email_field.comment == "이메일 주소"


def test_scan_java_class_fields_with_final(tmp_path):
    """private final 필드에서 final을 제거하고 타입만 추출"""
    java_file = tmp_path / "FinalFields.java"
    java_file.write_text(
        "public class FinalFields {\n"
        "    // 서비스\n"
        "    private final UserService userService;\n"
        "    // 이름\n"
        "    private String name;\n"
        "}\n"
    )
    _, _, class_fields = scan_java([java_file])
    assert "FinalFields" in class_fields
    fields = class_fields["FinalFields"]
    svc = next(f for f in fields if f.name == "userService")
    assert svc.type == "UserService"  # final이 제거된 타입
    assert svc.comment == "서비스"


def test_scan_java_request_fields_resolved():
    """@RequestBody 타입의 필드가 requestFields로 해석됨"""
    endpoints, modules, class_fields = scan_java([
        FIXTURE_DIR / "UserController.java",
        FIXTURE_DIR / "UserService.java",
        FIXTURE_DIR / "User.java",
    ])
    post = next((ep for ep in endpoints if ep.method == "POST"), None)
    assert post is not None
    assert len(post.requestFields) > 0
    assert any(f.name == "email" for f in post.requestFields)


def test_scan_java_response_fields_resolved():
    """반환 타입 ApiResponse<User> 또는 List<User>에서 User 필드가 responseFields로 해석됨"""
    endpoints, modules, class_fields = scan_java([
        FIXTURE_DIR / "UserController.java",
        FIXTURE_DIR / "UserService.java",
        FIXTURE_DIR / "User.java",
    ])
    get_all = next((ep for ep in endpoints if ep.method == "GET" and ep.path == "/api/users"), None)
    assert get_all is not None
    assert len(get_all.responseFields) > 0
    assert any(f.name == "id" for f in get_all.responseFields)


def test_scan_java_response_fields_unresolved():
    """알 수 없는 타입이면 responseFields는 빈 리스트"""
    endpoints, modules, class_fields = scan_java([
        FIXTURE_DIR / "UserController.java",
        FIXTURE_DIR / "UserService.java",
        # User.java 미포함 → resolve 불가
    ])
    get_all = next((ep for ep in endpoints if ep.method == "GET" and ep.path == "/api/users"), None)
    assert get_all is not None
    assert get_all.responseFields == []
```

- [ ] **Step 5: Run tests to verify they fail**

Run: `uv run pytest tests/scanner/test_java_scanner.py::test_scan_java_class_fields -v`
Expected: FAIL — `scan_java` returns 2 values, not 3

- [ ] **Step 6: Implement changes**

**핵심 변경 사항:**

1. `scan_java()` 반환값을 `tuple[list[Endpoint], list[Module]]`에서 `tuple[list[Endpoint], list[Module], dict[str, list[JavaField]]]`로 변경

2. 모든 Java 클래스(어노테이션 유무 관계없이)에서 필드를 파싱하는 `_parse_class_fields()` 함수 추가:

```python
from codemap.models import Endpoint, Module, Param, JavaField

# 필드 패턴: private [final] Type fieldName;
_FIELD_RE = re.compile(r"private\s+(?:final\s+)?([\w<>,\s\?]+?)\s+(\w+)\s*;")
# 바로 윗줄 주석: // comment
_LINE_COMMENT_RE = re.compile(r"^\s*//\s*(.+)$")


def _parse_class_fields(source: str) -> list[JavaField]:
    """Extract private fields with their line comments from a Java class."""
    fields: list[JavaField] = []
    lines = source.split("\n")
    for i, line in enumerate(lines):
        m = _FIELD_RE.search(line)
        if not m:
            continue
        field_type = m.group(1).strip()
        field_name = m.group(2)
        # Check previous line for // comment
        comment = ""
        if i > 0:
            cm = _LINE_COMMENT_RE.match(lines[i - 1])
            if cm:
                comment = cm.group(1).strip()
        fields.append(JavaField(name=field_name, type=field_type, comment=comment))
    return fields
```

3. `_parse_java_file()`에서 어노테이션이 없는 클래스도 파싱하도록 수정. 기존 로직은 `@RestController` 등이 없으면 `None`을 반환하는데, 필드 파싱은 별도 경로로 처리:

```python
def scan_java(java_files: list[Path]) -> tuple[list[Endpoint], list[Module], dict[str, list[JavaField]]]:
    if not java_files:
        return [], [], {}

    class_info: dict[str, dict] = {}
    class_fields: dict[str, list[JavaField]] = {}  # NEW

    for java_file in java_files:
        try:
            source = java_file.read_text(encoding="utf-8")
        except Exception as e:
            logger.warning(f"Failed to read {java_file}: {e}")
            continue

        # Parse annotated classes (controllers, services, etc.)
        info = _parse_java_file(source, java_file)
        if info:
            class_info[info["name"]] = info

        # Parse ALL class fields (Entity, DTO, etc.)
        class_name_match = _CLASS_NAME_RE.search(source)
        if class_name_match:
            cls_name = class_name_match.group(1)
            fields = _parse_class_fields(source)
            if fields:
                class_fields[cls_name] = fields

    # ... 기존 modules 빌드 로직 ...
    # ... 기존 endpoints 빌드 로직 ...

    # Resolve request/response fields for each endpoint
    for ep in endpoints:
        ep.requestFields = _resolve_request_fields(ep, class_fields)
        ep.responseFields = _resolve_response_fields(ep, class_fields)

    return endpoints, modules, class_fields
```

4. 타입 해석 함수:

```python
def _extract_inner_type(type_str: str) -> str:
    """Extract inner type from generics: 'ApiResponse<List<User>>' → 'User', 'List<User>' → 'User', 'User' → 'User'"""
    # Strip outer ApiResponse<...>
    m = re.match(r"ApiResponse<(.+)>", type_str)
    if m:
        type_str = m.group(1).strip()
    # Strip List<...>
    m = re.match(r"(?:List|Set|Collection)<(.+)>", type_str)
    if m:
        type_str = m.group(1).strip()
    return type_str


def _resolve_request_fields(ep: Endpoint, class_fields: dict[str, list[JavaField]]) -> list[JavaField]:
    """Resolve @RequestBody type to class fields."""
    for p in ep.params:
        if p.annotation == "RequestBody" and p.type in class_fields:
            return class_fields[p.type]
    return []


def _resolve_response_fields(ep: Endpoint, class_fields: dict[str, list[JavaField]]) -> list[JavaField]:
    """Resolve return type to class fields."""
    if not ep.returnType:
        return []
    inner_type = _extract_inner_type(ep.returnType)
    return class_fields.get(inner_type, [])
```

5. **중요:** `scan_java()`의 반환값이 3-tuple로 바뀌므로, 호출하는 곳도 모두 수정해야 함:

`src/codemap/scanner/__init__.py` (line 33):
```python
# 기존: endpoints, modules = scan_java(java_files)
# 변경:
endpoints, modules, class_fields = scan_java(java_files)
```

그리고 `run_scan()`에서 `class_fields`를 `ApiSchema`에 저장:
```python
if scan_all or "api" in targets:
    result.api = ApiSchema(endpoints=endpoints, classFields=class_fields)
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `uv run pytest tests/scanner/test_java_scanner.py -v`
Expected: All PASS (기존 + 신규)

- [ ] **Step 8: Run full test suite to check nothing broke**

Run: `uv run pytest tests/ -v --tb=short`
Expected: All PASS (scanner/__init__.py 변경으로 CLI/integration 테스트도 확인)

- [ ] **Step 9: Commit**

```bash
git add src/codemap/scanner/java_scanner.py src/codemap/scanner/__init__.py tests/scanner/test_java_scanner.py tests/fixtures/User.java tests/fixtures/UserRequest.java
git commit -m "feat: parse Java class fields and resolve request/response types"
```

---

## Task 3: API 명세서 상세 출력

**Files:**
- Modify: `src/codemap/doc/api_spec.py`
- Modify: `tests/doc/test_api_spec.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/doc/test_api_spec.py — import에 JavaField 추가

def test_api_spec_detailed_endpoint():
    """엔드포인트별 섹션에 입력/응답 필드 테이블이 출력됨"""
    api = ApiSchema(endpoints=[
        Endpoint(
            method="GET", path="/api/devices",
            controller="DeviceApiController", service="DeviceService",
            params=[Param(name="deviceType", type="String", annotation="RequestParam", required=False)],
            returnType="ApiResponse<List<Device>>",
            responseFields=[
                JavaField(name="deviceId", type="Integer", comment="고유번호"),
                JavaField(name="deviceName", type="String", comment="장비명"),
                JavaField(name="status", type="String", comment="상태"),
            ],
        ),
    ])
    md = generate_api_spec(api)
    # 엔드포인트별 섹션 헤더
    assert "## GET /api/devices" in md
    # 입력 파라미터 테이블
    assert "deviceType" in md
    assert "RequestParam" in md
    # 응답 필드 테이블
    assert "deviceId" in md
    assert "고유번호" in md
    assert "장비명" in md


def test_api_spec_detailed_request_body():
    """@RequestBody 엔드포인트에 requestFields 테이블이 출력됨"""
    api = ApiSchema(endpoints=[
        Endpoint(
            method="POST", path="/api/users",
            controller="UserController", service="UserService",
            params=[Param(name="user", type="User", annotation="RequestBody")],
            returnType="ApiResponse<User>",
            requestFields=[
                JavaField(name="email", type="String", comment="이메일 주소"),
                JavaField(name="name", type="String", comment="사용자명"),
            ],
            responseFields=[
                JavaField(name="id", type="Long", comment="고유번호"),
                JavaField(name="email", type="String", comment="이메일 주소"),
            ],
        ),
    ])
    md = generate_api_spec(api)
    assert "## POST /api/users" in md
    assert "### 요청 본문" in md or "### 입력" in md
    assert "이메일 주소" in md
    assert "### 응답" in md
    assert "고유번호" in md


def test_api_spec_detailed_no_fields():
    """필드 정보가 없는 엔드포인트는 기본 정보만 표시"""
    api = ApiSchema(endpoints=[
        Endpoint(
            method="GET", path="/api/health",
            controller="HealthController", service="",
            returnType="String",
        ),
    ])
    md = generate_api_spec(api)
    assert "## GET /api/health" in md


def test_api_spec_summary_table():
    """상단에 요약 테이블이 포함됨"""
    api = ApiSchema(endpoints=[
        Endpoint(method="GET", path="/api/test", controller="C", service="S"),
    ])
    md = generate_api_spec(api)
    assert "# API 명세서" in md
    # 요약 테이블
    assert "| 메서드 |" in md or "메서드" in md
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/doc/test_api_spec.py::test_api_spec_detailed_endpoint -v`
Expected: FAIL

- [ ] **Step 3: Implement new api_spec.py**

```python
# src/codemap/doc/api_spec.py
from codemap.models import ApiSchema, Endpoint


def generate_api_spec(api: ApiSchema) -> str:
    lines: list[str] = ["# API 명세서", ""]

    # 요약 테이블
    lines.append("## 요약")
    lines.append("")
    lines.append("| No | 메서드 | 경로 | 컨트롤러 | 서비스 | 반환 타입 |")
    lines.append("|----|--------|------|----------|--------|----------|")
    for i, ep in enumerate(api.endpoints, 1):
        lines.append(
            f"| {i} | {ep.method} | {ep.path} | {ep.controller} | {ep.service} | {ep.returnType} |"
        )
    lines.append("")

    # 엔드포인트별 상세
    for ep in api.endpoints:
        lines.append(f"## {ep.method} {ep.path}")
        lines.append("")
        lines.append(f"- **컨트롤러:** {ep.controller}")
        if ep.service:
            lines.append(f"- **서비스:** {ep.service}")
        if ep.returnType:
            lines.append(f"- **반환 타입:** `{ep.returnType}`")
        lines.append("")

        # 입력 파라미터 (RequestParam, PathVariable)
        query_params = [p for p in ep.params if p.annotation != "RequestBody"]
        body_params = [p for p in ep.params if p.annotation == "RequestBody"]

        if query_params:
            lines.append("### 입력 파라미터")
            lines.append("")
            lines.append("| 파라미터명 | 타입 | 어노테이션 | 필수 |")
            lines.append("|-----------|------|-----------|------|")
            for p in query_params:
                req = "Y" if p.required else "N"
                lines.append(f"| {p.name} | {p.type} | @{p.annotation} | {req} |")
            lines.append("")

        # 요청 본문 (@RequestBody)
        if body_params or ep.requestFields:
            lines.append("### 요청 본문")
            lines.append("")
            if body_params:
                p = body_params[0]
                lines.append(f"**타입:** `{p.type}`")
                lines.append("")
            if ep.requestFields:
                lines.append("| 필드명 | 타입 | 설명 |")
                lines.append("|--------|------|------|")
                for f in ep.requestFields:
                    lines.append(f"| {f.name} | {f.type} | {f.comment} |")
                lines.append("")

        # 응답
        if ep.responseFields:
            lines.append("### 응답")
            lines.append("")
            lines.append("| 필드명 | 타입 | 설명 |")
            lines.append("|--------|------|------|")
            for f in ep.responseFields:
                lines.append(f"| {f.name} | {f.type} | {f.comment} |")
            lines.append("")

        lines.append("---")
        lines.append("")

    return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/doc/test_api_spec.py -v`
Expected: All PASS (기존 + 신규)

- [ ] **Step 5: Commit**

```bash
git add src/codemap/doc/api_spec.py tests/doc/test_api_spec.py
git commit -m "feat: generate per-endpoint API spec with expanded request/response fields"
```

---

## Task 4: Excel API 시트 상세화

**Files:**
- Modify: `src/codemap/export/xlsx.py`
- Modify: `tests/export/test_xlsx.py`

- [ ] **Step 1: Write failing test**

```python
# tests/export/test_xlsx.py 에 추가

def test_export_api_spec_xlsx_detailed(tmp_path):
    """엔드포인트별 시트에 요청/응답 필드가 포함됨"""
    from codemap.models import JavaField, Param
    scan = ScanResult(
        project="test",
        api=ApiSchema(endpoints=[
            Endpoint(
                method="GET", path="/api/devices",
                controller="DeviceApiController", service="DeviceService",
                params=[Param(name="deviceType", type="String", annotation="RequestParam", required=False)],
                returnType="ApiResponse<List<Device>>",
                responseFields=[
                    JavaField(name="deviceId", type="Integer", comment="고유번호"),
                    JavaField(name="deviceName", type="String", comment="장비명"),
                ],
            ),
            Endpoint(
                method="POST", path="/api/users",
                controller="UserController", service="UserService",
                params=[Param(name="user", type="User", annotation="RequestBody")],
                returnType="ApiResponse<User>",
                requestFields=[
                    JavaField(name="email", type="String", comment="이메일"),
                ],
                responseFields=[
                    JavaField(name="id", type="Long", comment="고유번호"),
                ],
            ),
        ]),
    )
    output = tmp_path / "api-detail.xlsx"
    export_api_spec_xlsx(scan, output)
    wb = openpyxl.load_workbook(output)
    # 요약 시트 + 엔드포인트별 시트
    assert "엔드포인트 목록" in wb.sheetnames
    assert len(wb.sheetnames) >= 3  # 목록 + 2 endpoints
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/export/test_xlsx.py::test_export_api_spec_xlsx_detailed -v`
Expected: FAIL

- [ ] **Step 3: Implement xlsx changes**

`export_api_spec_xlsx` 함수를 수정:
1. 기존 "엔드포인트 목록" 시트는 요약으로 유지
2. 각 엔드포인트에 대해 별도 시트를 생성 (시트명: `{method} {path}` 앞 31자 잘림)
3. 각 시트에 기본 정보 + 입력 파라미터 테이블 + 요청 본문 필드 테이블 + 응답 필드 테이블

```python
def export_api_spec_xlsx(scan: ScanResult, output: Path) -> None:
    wb = openpyxl.Workbook()

    # --- 요약 시트 ---
    ws = wb.active
    ws.title = "엔드포인트 목록"
    headers = ["No", "메서드", "경로", "컨트롤러", "서비스", "반환 타입"]
    for ci, h in enumerate(headers, 1):
        ws.cell(row=1, column=ci, value=h)
    _style_header_row(ws, 1, len(headers))

    for ei, ep in enumerate(scan.api.endpoints, 1):
        row = ei + 1
        ws.cell(row=row, column=1, value=ei)
        ws.cell(row=row, column=2, value=ep.method)
        ws.cell(row=row, column=3, value=ep.path)
        ws.cell(row=row, column=4, value=ep.controller)
        ws.cell(row=row, column=5, value=ep.service)
        ws.cell(row=row, column=6, value=ep.returnType)
        _apply_border(ws, row, len(headers))
    _auto_width(ws)

    # --- 엔드포인트별 상세 시트 ---
    for ei, ep in enumerate(scan.api.endpoints, 1):
        sheet_name = f"{ep.method} {ep.path}"[:31]  # Excel 시트명 31자 제한
        ws_ep = wb.create_sheet(title=sheet_name)
        row = 1

        # 기본 정보
        ws_ep.cell(row=row, column=1, value="메서드")
        ws_ep.cell(row=row, column=2, value=ep.method)
        row += 1
        ws_ep.cell(row=row, column=1, value="경로")
        ws_ep.cell(row=row, column=2, value=ep.path)
        row += 1
        ws_ep.cell(row=row, column=1, value="컨트롤러")
        ws_ep.cell(row=row, column=2, value=ep.controller)
        row += 1
        ws_ep.cell(row=row, column=1, value="서비스")
        ws_ep.cell(row=row, column=2, value=ep.service)
        row += 1
        ws_ep.cell(row=row, column=1, value="반환 타입")
        ws_ep.cell(row=row, column=2, value=ep.returnType)
        row += 2

        # 입력 파라미터
        query_params = [p for p in ep.params if p.annotation != "RequestBody"]
        if query_params:
            ws_ep.cell(row=row, column=1, value="입력 파라미터")
            ws_ep.cell(row=row, column=1).font = Font(bold=True)
            row += 1
            param_headers = ["파라미터명", "타입", "어노테이션", "필수"]
            for ci, h in enumerate(param_headers, 1):
                ws_ep.cell(row=row, column=ci, value=h)
            _style_header_row(ws_ep, row, len(param_headers))
            row += 1
            for p in query_params:
                ws_ep.cell(row=row, column=1, value=p.name)
                ws_ep.cell(row=row, column=2, value=p.type)
                ws_ep.cell(row=row, column=3, value=f"@{p.annotation}")
                ws_ep.cell(row=row, column=4, value="Y" if p.required else "N")
                _apply_border(ws_ep, row, len(param_headers))
                row += 1
            row += 1

        # 요청 본문
        if ep.requestFields:
            ws_ep.cell(row=row, column=1, value="요청 본문")
            ws_ep.cell(row=row, column=1).font = Font(bold=True)
            row += 1
            field_headers = ["필드명", "타입", "설명"]
            for ci, h in enumerate(field_headers, 1):
                ws_ep.cell(row=row, column=ci, value=h)
            _style_header_row(ws_ep, row, len(field_headers))
            row += 1
            for f in ep.requestFields:
                ws_ep.cell(row=row, column=1, value=f.name)
                ws_ep.cell(row=row, column=2, value=f.type)
                ws_ep.cell(row=row, column=3, value=f.comment)
                _apply_border(ws_ep, row, len(field_headers))
                row += 1
            row += 1

        # 응답
        if ep.responseFields:
            ws_ep.cell(row=row, column=1, value="응답")
            ws_ep.cell(row=row, column=1).font = Font(bold=True)
            row += 1
            field_headers = ["필드명", "타입", "설명"]
            for ci, h in enumerate(field_headers, 1):
                ws_ep.cell(row=row, column=ci, value=h)
            _style_header_row(ws_ep, row, len(field_headers))
            row += 1
            for f in ep.responseFields:
                ws_ep.cell(row=row, column=1, value=f.name)
                ws_ep.cell(row=row, column=2, value=f.type)
                ws_ep.cell(row=row, column=3, value=f.comment)
                _apply_border(ws_ep, row, len(field_headers))
                row += 1

        _auto_width(ws_ep)

    wb.save(output)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/export/test_xlsx.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/codemap/export/xlsx.py tests/export/test_xlsx.py
git commit -m "feat: generate per-endpoint xlsx sheets with request/response field detail"
```

---

## Task 5: 전체 테스트 + 실제 프로젝트 검증

**Files:**
- No new files

- [ ] **Step 1: Run full test suite**

Run: `uv run pytest tests/ -v --tb=short`
Expected: All PASS

- [ ] **Step 2: Verify against iuu project — class fields**

```bash
uv run codemap --verbose scan /home/ashzero/repository/iuu --target api -o /tmp/codemap-verify2/scan.json
uv run python3 -c "
import json
data = json.load(open('/tmp/codemap-verify2/scan.json'))
cf = data['api'].get('classFields', {})
print(f'파싱된 클래스 수: {len(cf)}')
for name in list(cf.keys())[:5]:
    fields = cf[name]
    print(f'  {name}: {len(fields)} fields')
    for f in fields[:3]:
        print(f'    - {f[\"name\"]}: {f[\"type\"]} ({f.get(\"comment\", \"\")})')
"
```
Expected: Device, BlackboxLog 등의 클래스 필드가 한국어 주석과 함께 출력

- [ ] **Step 3: Verify API spec doc output**

```bash
uv run codemap generate /home/ashzero/repository/iuu -o /tmp/codemap-verify2/output --target all --format drawio --export xlsx
head -60 /tmp/codemap-verify2/output/docs/api-spec.md
```
Expected: 엔드포인트별 섹션, 입력 파라미터 테이블, 응답 필드 테이블이 한국어 설명과 함께 출력

- [ ] **Step 4: Commit if fixes needed**

```bash
git add -A
git commit -m "fix: address issues found during integration verification"
```
