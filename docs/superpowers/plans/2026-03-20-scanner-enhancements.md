# Scanner Enhancements: SQL Comment + API Params/Response

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** (1) SQL 스캐너가 `COMMENT ON TABLE/COLUMN` 구문을 파싱하여 테이블/컬럼 설명을 채우고, (2) Java 스캐너가 컨트롤러 메서드의 `@RequestParam`/`@RequestBody`/`@PathVariable` 파라미터와 반환 타입(`ApiResponse<T>`)을 추출하여 API 명세에 포함한다.

**Architecture:** 모델에 `comment`/`params`/`returnType` 필드를 추가하고, 각 스캐너에서 추출 로직을 확장한 뒤, doc/export 레이어에 반영한다. 기존 테스트는 그대로 통과해야 하며, 새 필드는 optional이므로 하위 호환성이 유지된다.

**Tech Stack:** Python 3.12, regex (SQL COMMENT 파싱은 sqlglot이 지원하지 않으므로), Pydantic, openpyxl

**Spec:** iuu 프로젝트의 실제 DDL과 Spring Controller를 레퍼런스로 사용

---

## File Structure

```
src/codemap/
├── models.py                      # Column.comment, Table.comment, Endpoint.params, Endpoint.returnType 추가
├── scanner/
│   ├── sql_scanner.py             # COMMENT ON TABLE/COLUMN 파싱 추가
│   └── java_scanner.py            # 메서드 시그니처에서 params/returnType 추출
├── doc/
│   ├── table_spec.py              # 설명 컬럼에 comment 출력
│   └── api_spec.py                # params, returnType 컬럼 추가
└── export/
    └── xlsx.py                    # 설명 컬럼에 comment 출력, API 시트에 params/returnType 추가
tests/
├── fixtures/
│   ├── sample_with_comments.sql   # COMMENT ON 구문 포함 DDL fixture
│   └── UserController.java        # 기존 fixture에 @RequestParam 추가 버전
├── scanner/
│   ├── test_sql_scanner.py        # comment 파싱 테스트 추가
│   └── test_java_scanner.py       # params/returnType 테스트 추가
├── doc/
│   ├── test_table_spec.py         # comment 출력 테스트 추가
│   └── test_api_spec.py           # params/returnType 출력 테스트 추가
└── export/
    └── test_xlsx.py               # comment/params/returnType 반영 테스트 추가
```

---

## Task 1: 모델 확장 — comment, params, returnType 필드 추가

**Files:**
- Modify: `src/codemap/models.py`
- Modify: `tests/test_models.py`

- [ ] **Step 1: Write failing tests for new fields**

```python
# tests/test_models.py — import 블록에 Param 추가:
# from codemap.models import (...기존..., Param)

def test_column_comment():
    col = Column(name="id", type="BIGINT", pk=True, nullable=False, comment="고유번호")
    assert col.comment == "고유번호"


def test_column_comment_default():
    col = Column(name="id", type="BIGINT")
    assert col.comment == ""


def test_table_comment():
    table = Table(name="users", comment="사용자 관리")
    assert table.comment == "사용자 관리"


def test_endpoint_params():
    ep = Endpoint(
        method="GET",
        path="/api/devices",
        controller="DeviceApiController",
        service="DeviceService",
        params=[
            Param(name="deviceType", type="String", annotation="RequestParam", required=False),
        ],
        returnType="ApiResponse<List<Device>>",
    )
    assert len(ep.params) == 1
    assert ep.params[0].annotation == "RequestParam"
    assert ep.returnType == "ApiResponse<List<Device>>"


def test_endpoint_params_default():
    ep = Endpoint(method="GET", path="/api/test", controller="C", service="S")
    assert ep.params == []
    assert ep.returnType == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_models.py::test_column_comment -v`
Expected: FAIL — `TypeError: Column() got an unexpected keyword argument 'comment'`

- [ ] **Step 3: Implement model changes**

```python
# src/codemap/models.py — 변경 사항

class Column(BaseModel):
    name: str
    type: str
    pk: bool = False
    nullable: bool = True
    comment: str = ""          # NEW


class Table(BaseModel):
    name: str
    comment: str = ""          # NEW
    columns: list[Column] = Field(default_factory=list)
    foreignKeys: list[ForeignKey] = Field(default_factory=list)
    indexes: list[Index] = Field(default_factory=list)


class Param(BaseModel):        # NEW
    name: str
    type: str
    annotation: str            # "RequestParam" | "RequestBody" | "PathVariable"
    required: bool = True


class Endpoint(BaseModel):
    method: str
    path: str
    controller: str
    service: str
    calls: list[str] = Field(default_factory=list)
    params: list[Param] = Field(default_factory=list)      # NEW
    returnType: str = ""                                     # NEW
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_models.py -v`
Expected: All PASS (기존 테스트 포함)

- [ ] **Step 5: Commit**

```bash
git add src/codemap/models.py tests/test_models.py
git commit -m "feat: add comment, params, returnType fields to scan models"
```

---

## Task 2: SQL 스캐너 — COMMENT ON 파싱

**Files:**
- Modify: `src/codemap/scanner/sql_scanner.py`
- Create: `tests/fixtures/sample_with_comments.sql`
- Modify: `tests/scanner/test_sql_scanner.py`

- [ ] **Step 1: Create SQL fixture with COMMENT ON**

```sql
-- tests/fixtures/sample_with_comments.sql
CREATE TABLE departments (
    id BIGINT PRIMARY KEY,
    name VARCHAR(255) NOT NULL
);

COMMENT ON TABLE departments IS '부서 관리';
COMMENT ON COLUMN departments.id IS '부서 고유번호';
COMMENT ON COLUMN departments.name IS '부서명';

CREATE TABLE users (
    id BIGINT PRIMARY KEY,
    email VARCHAR(255) NOT NULL,
    dept_id BIGINT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_users_dept FOREIGN KEY (dept_id) REFERENCES departments(id)
);

COMMENT ON TABLE users IS '사용자 관리';
COMMENT ON COLUMN users.id IS '사용자 고유번호';
COMMENT ON COLUMN users.email IS '이메일 주소';
COMMENT ON COLUMN users.dept_id IS '소속 부서 ID';
COMMENT ON COLUMN users.created_at IS '가입일';

CREATE UNIQUE INDEX idx_users_email ON users(email);
```

- [ ] **Step 2: Write failing tests**

```python
# tests/scanner/test_sql_scanner.py 에 추가
def test_scan_sql_table_comment():
    tables = scan_sql([FIXTURE_DIR / "sample_with_comments.sql"])
    depts = next(t for t in tables if t.name == "departments")
    assert depts.comment == "부서 관리"
    users = next(t for t in tables if t.name == "users")
    assert users.comment == "사용자 관리"


def test_scan_sql_column_comments():
    tables = scan_sql([FIXTURE_DIR / "sample_with_comments.sql"])
    users = next(t for t in tables if t.name == "users")
    id_col = next(c for c in users.columns if c.name == "id")
    assert id_col.comment == "사용자 고유번호"
    email_col = next(c for c in users.columns if c.name == "email")
    assert email_col.comment == "이메일 주소"
    dept_col = next(c for c in users.columns if c.name == "dept_id")
    assert dept_col.comment == "소속 부서 ID"


def test_scan_sql_no_comment_is_empty():
    """기존 sample.sql에는 COMMENT ON이 없으므로 comment는 빈 문자열"""
    tables = scan_sql([FIXTURE_DIR / "sample.sql"])
    users = next(t for t in tables if t.name == "users")
    assert users.comment == ""
    assert all(c.comment == "" for c in users.columns)


def test_scan_sql_comment_escaped_quote(tmp_path):
    """COMMENT에 escaped single quote 처리"""
    sql = tmp_path / "escaped.sql"
    sql.write_text(
        "CREATE TABLE t1 (id INT);\n"
        "COMMENT ON TABLE t1 IS 'it''s a table';\n"
        "COMMENT ON COLUMN t1.id IS 'the ID''s value';\n"
    )
    tables = scan_sql([sql])
    assert tables[0].comment == "it's a table"
    assert tables[0].columns[0].comment == "the ID's value"


def test_scan_sql_comment_schema_qualified(tmp_path):
    """COMMENT ON TABLE public.t1 형태 처리"""
    sql = tmp_path / "schema.sql"
    sql.write_text(
        "CREATE TABLE t1 (id INT);\n"
        "COMMENT ON TABLE public.t1 IS '스키마 지정 테이블';\n"
        "COMMENT ON COLUMN public.t1.id IS '스키마 지정 컬럼';\n"
    )
    tables = scan_sql([sql])
    assert tables[0].comment == "스키마 지정 테이블"
    assert tables[0].columns[0].comment == "스키마 지정 컬럼"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/scanner/test_sql_scanner.py::test_scan_sql_table_comment -v`
Expected: FAIL — comment가 비어있음

- [ ] **Step 4: Implement COMMENT ON parsing**

`COMMENT ON TABLE/COLUMN` 구문은 sqlglot이 PostgreSQL dialect에서 `exp.Comment`로 파싱하지 않으므로, regex로 직접 파싱한다. `scan_sql()` 함수의 끝에서 raw SQL 텍스트를 대상으로 COMMENT ON 구문을 매칭하여 table/column에 comment를 채운다.

```python
# src/codemap/scanner/sql_scanner.py 에 추가

import re

# COMMENT ON TABLE [schema.]table_name IS 'comment'; (handles escaped '' quotes)
_COMMENT_TABLE_RE = re.compile(
    r"comment\s+on\s+table\s+(?:\w+\.)?(\w+)\s+is\s+'((?:[^']|'')*)'",
    re.IGNORECASE,
)

# COMMENT ON COLUMN [schema.]table_name.column_name IS 'comment';
_COMMENT_COLUMN_RE = re.compile(
    r"comment\s+on\s+column\s+(?:\w+\.)?(\w+)\.(\w+)\s+is\s+'((?:[^']|'')*)'",
    re.IGNORECASE,
)


def _apply_comments(tables: list[Table], sql_texts: list[str]) -> None:
    """Parse COMMENT ON statements from raw SQL and apply to tables/columns."""
    table_comments: dict[str, str] = {}
    column_comments: dict[tuple[str, str], str] = {}

    for sql_text in sql_texts:
        for m in _COMMENT_TABLE_RE.finditer(sql_text):
            table_comments[m.group(1)] = m.group(2).replace("''", "'")
        for m in _COMMENT_COLUMN_RE.finditer(sql_text):
            column_comments[(m.group(1), m.group(2))] = m.group(3).replace("''", "'")

    for table in tables:
        if table.name in table_comments:
            table.comment = table_comments[table.name]
        for col in table.columns:
            key = (table.name, col.name)
            if key in column_comments:
                col.comment = column_comments[key]
```

`scan_sql()` 함수를 수정하여 raw SQL 텍스트를 수집하고 마지막에 `_apply_comments()`를 호출:

```python
def scan_sql(sql_files: list[Path]) -> list[Table]:
    tables: list[Table] = []
    indexes: dict[str, list[Index]] = {}
    raw_texts: list[str] = []          # NEW

    for sql_file in sql_files:
        try:
            sql_text = sql_file.read_text(encoding="utf-8")
            raw_texts.append(sql_text)  # NEW
            statements = sqlglot.parse(sql_text)
        except Exception as e:
            logger.warning(f"Failed to parse {sql_file}: {e}")
            continue

        # ... 기존 로직 유지 ...

    # Attach indexes to tables
    for table in tables:
        if table.name in indexes:
            table.indexes.extend(indexes[table.name])

    # Apply COMMENT ON
    _apply_comments(tables, raw_texts)  # NEW

    return tables
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/scanner/test_sql_scanner.py -v`
Expected: All PASS (기존 + 신규)

- [ ] **Step 6: Commit**

```bash
git add src/codemap/scanner/sql_scanner.py tests/scanner/test_sql_scanner.py tests/fixtures/sample_with_comments.sql
git commit -m "feat: parse COMMENT ON TABLE/COLUMN in SQL scanner"
```

---

## Task 3: Java 스캐너 — params/returnType 추출

**Files:**
- Modify: `src/codemap/scanner/java_scanner.py`
- Modify: `tests/fixtures/UserController.java`
- Modify: `tests/scanner/test_java_scanner.py`

- [ ] **Step 1: Update Java fixture with params and return types**

기존 `tests/fixtures/UserController.java`를 수정하여 `@RequestParam`, `@RequestBody`, `@PathVariable`과 명시적 반환 타입을 포함한다:

```java
// tests/fixtures/UserController.java
package com.example.user;

import org.springframework.web.bind.annotation.*;
import java.util.List;

@RestController
@RequestMapping("/api/users")
public class UserController {

    private final UserService userService;

    public UserController(UserService userService) {
        this.userService = userService;
    }

    @GetMapping
    public ApiResponse<List<User>> getUsers(@RequestParam(required = false) String status) {
        return userService.findAll();
    }

    @PostMapping
    public ApiResponse<User> createUser(@RequestBody User user) {
        return userService.create(user);
    }

    @GetMapping("/{id}")
    public ApiResponse<User> getUser(@PathVariable Long id) {
        return userService.findById(id);
    }
}
```

- [ ] **Step 2: Write failing tests**

```python
# tests/scanner/test_java_scanner.py 에 추가
def test_scan_java_endpoint_params():
    endpoints, _ = scan_java(
        [FIXTURE_DIR / "UserController.java", FIXTURE_DIR / "UserService.java"]
    )
    get_all = next((ep for ep in endpoints if ep.method == "GET" and ep.path == "/api/users"), None)
    assert get_all is not None
    assert len(get_all.params) == 1
    assert get_all.params[0].name == "status"
    assert get_all.params[0].annotation == "RequestParam"
    assert get_all.params[0].required is False


def test_scan_java_endpoint_request_body():
    endpoints, _ = scan_java(
        [FIXTURE_DIR / "UserController.java", FIXTURE_DIR / "UserService.java"]
    )
    post = next((ep for ep in endpoints if ep.method == "POST"), None)
    assert post is not None
    assert len(post.params) == 1
    assert post.params[0].annotation == "RequestBody"
    assert post.params[0].type == "User"


def test_scan_java_endpoint_path_variable():
    endpoints, _ = scan_java(
        [FIXTURE_DIR / "UserController.java", FIXTURE_DIR / "UserService.java"]
    )
    get_by_id = next((ep for ep in endpoints if "/{id}" in ep.path or ep.path.endswith("/{id}")), None)
    assert get_by_id is not None
    assert any(p.annotation == "PathVariable" for p in get_by_id.params)


def test_scan_java_return_type():
    endpoints, _ = scan_java(
        [FIXTURE_DIR / "UserController.java", FIXTURE_DIR / "UserService.java"]
    )
    get_all = next((ep for ep in endpoints if ep.method == "GET" and ep.path == "/api/users"), None)
    assert get_all is not None
    assert "List<User>" in get_all.returnType or "ApiResponse" in get_all.returnType


def test_scan_java_return_type_default():
    """기존 endpoint_stubs에 returnType이 없으면 빈 문자열"""
    endpoints, _ = scan_java([])
    # Empty input should not crash
    assert endpoints == []


def test_scan_java_multi_params(tmp_path):
    """메서드에 여러 파라미터가 있는 경우"""
    java_file = tmp_path / "MultiController.java"
    java_file.write_text(
        '@RestController\n@RequestMapping("/api/search")\n'
        'public class MultiController {\n'
        '    @GetMapping\n'
        '    public ApiResponse<List<Item>> search(\n'
        '            @RequestParam String keyword,\n'
        '            @RequestParam(required = false) Integer page) {\n'
        '        return null;\n'
        '    }\n'
        '}\n'
    )
    endpoints, _ = scan_java([java_file])
    assert len(endpoints) == 1
    assert len(endpoints[0].params) == 2
    assert endpoints[0].params[0].name == "keyword"
    assert endpoints[0].params[0].required is True
    assert endpoints[0].params[1].name == "page"
    assert endpoints[0].params[1].required is False
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/scanner/test_java_scanner.py::test_scan_java_endpoint_params -v`
Expected: FAIL

- [ ] **Step 4: Implement param/returnType extraction**

Java 스캐너의 `_extract_endpoint_stubs()`를 확장하여 각 매핑 메서드의 파라미터와 반환 타입을 추출한다.

핵심 변경:
1. `_METHOD_MAPPING_RE`로 매핑 어노테이션 위치를 찾은 후, 해당 메서드 시그니처 전체를 추출
2. 메서드 시그니처에서 반환 타입 (public 다음 ~ 메서드명 사이)과 파라미터 (`@RequestParam`, `@RequestBody`, `@PathVariable` 포함) 를 regex로 파싱
3. `endpoint_stubs`를 `(method, path)` 대신 `(method, path, params, return_type)` 튜플로 변경

```python
# src/codemap/scanner/java_scanner.py 에 추가/수정

from codemap.models import Endpoint, Module, Param

# 메서드 시그니처에서 파라미터 어노테이션 추출
_PARAM_ANNOTATION_RE = re.compile(
    r"@(RequestParam|RequestBody|PathVariable)"
    r"(?:\(([^)]*)\))?\s+"        # 옵션: (required = false) 등
    r"(\w+(?:<[^>]+>)?)\s+(\w+)"  # 타입 이름
)

# required = false 패턴
_REQUIRED_FALSE_RE = re.compile(r"required\s*=\s*false", re.IGNORECASE)


def _extract_endpoint_stubs(source: str) -> list[tuple[str, str, list[Param], str]]:
    """Extract (http_method, path, params, return_type) from method-level mapping annotations."""
    stubs = []
    lines = source.split("\n")

    for i, line in enumerate(lines):
        match = _METHOD_MAPPING_RE.search(line)
        if not match:
            continue

        http_verb = match.group(1)
        method_path = match.group(2) or ""
        http_method = _HTTP_METHOD_MAP.get(http_verb, http_verb.upper())

        # Find the method signature (may span multiple lines after annotation)
        method_sig = _find_method_signature(lines, i)
        params = _extract_method_params(method_sig)
        return_type = _extract_return_type(method_sig)

        stubs.append((http_method, method_path, params, return_type))
    return stubs


def _find_method_signature(lines: list[str], annotation_line: int) -> str:
    """Collect lines from annotation to the opening { of the method."""
    sig_parts = []
    for j in range(annotation_line, min(annotation_line + 10, len(lines))):
        sig_parts.append(lines[j])
        if "{" in lines[j]:
            break
    return " ".join(sig_parts)


def _extract_method_params(method_sig: str) -> list[Param]:
    """Extract @RequestParam/@RequestBody/@PathVariable parameters."""
    params = []
    for m in _PARAM_ANNOTATION_RE.finditer(method_sig):
        annotation = m.group(1)
        annotation_args = m.group(2) or ""
        param_type = m.group(3)
        param_name = m.group(4)
        required = not bool(_REQUIRED_FALSE_RE.search(annotation_args))
        params.append(Param(
            name=param_name,
            type=param_type,
            annotation=annotation,
            required=required,
        ))
    return params


def _extract_return_type(method_sig: str) -> str:
    """Extract return type from 'public ReturnType methodName(...)'"""
    m = re.search(r"public\s+([\w<>,\s\?]+?)\s+\w+\s*\(", method_sig)
    if m:
        return m.group(1).strip()
    return ""
```

`scan_java()` 함수에서 기존 2-tuple 언패킹을 4-tuple로 교체 (기존 line 97 `for http_method, method_path in info.get("endpoint_stubs", []):` 를 아래로 대체):

```python
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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/scanner/test_java_scanner.py -v`
Expected: All PASS (기존 + 신규)

- [ ] **Step 6: Commit**

```bash
git add src/codemap/scanner/java_scanner.py tests/scanner/test_java_scanner.py tests/fixtures/UserController.java
git commit -m "feat: extract request params and return type from Spring controllers"
```

---

## Task 4: Doc/Export 업데이트 — comment, params, returnType 출력

**Files:**
- Modify: `src/codemap/doc/table_spec.py`
- Modify: `src/codemap/doc/api_spec.py`
- Modify: `src/codemap/export/xlsx.py`
- Modify: `tests/doc/test_table_spec.py`
- Modify: `tests/doc/test_api_spec.py`
- Modify: `tests/export/test_xlsx.py`

- [ ] **Step 1: Write failing tests for table_spec comment output**

```python
# tests/doc/test_table_spec.py 에 추가
def test_table_spec_column_comment():
    from codemap.models import DatabaseSchema, Table, Column
    db = DatabaseSchema(tables=[
        Table(name="users", comment="사용자 관리", columns=[
            Column(name="id", type="BIGINT", pk=True, nullable=False, comment="고유번호"),
            Column(name="email", type="VARCHAR(255)", nullable=False, comment="이메일 주소"),
        ]),
    ])
    md = generate_table_spec(db)
    assert "고유번호" in md
    assert "이메일 주소" in md
    assert "사용자 관리" in md
```

- [ ] **Step 2: Write failing tests for api_spec params/returnType**

```python
# tests/doc/test_api_spec.py 에 추가 (import에 Param 추가 필요: from codemap.models import ApiSchema, Endpoint, Param)
def test_api_spec_params_and_return():
    from codemap.models import ApiSchema, Endpoint, Param
    api = ApiSchema(endpoints=[
        Endpoint(
            method="GET", path="/api/devices",
            controller="DeviceApiController", service="DeviceService",
            params=[Param(name="deviceType", type="String", annotation="RequestParam", required=False)],
            returnType="ApiResponse<List<Device>>",
        ),
    ])
    md = generate_api_spec(api)
    assert "deviceType" in md
    assert "RequestParam" in md
    assert "ApiResponse" in md or "List<Device>" in md
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/doc/test_table_spec.py::test_table_spec_column_comment tests/doc/test_api_spec.py::test_api_spec_params_and_return -v`
Expected: FAIL

- [ ] **Step 4: Implement table_spec comment output**

`src/codemap/doc/table_spec.py` 수정 — 테이블 comment를 헤더 아래에, 컬럼 comment를 설명 컬럼에 출력:

```python
def generate_table_spec(db: DatabaseSchema) -> str:
    lines: list[str] = ["# 테이블 정의서", ""]

    for table in db.tables:
        fk_map: dict[str, str] = {fk.column: fk.references for fk in table.foreignKeys}

        lines.append(f"## {table.name}")
        if table.comment:
            lines.append(f"\n{table.comment}")
        lines.append("")
        lines.append("### 컬럼")
        lines.append("")
        lines.append("| 컬럼명 | 타입 | PK | FK | Nullable | 설명 |")
        lines.append("|--------|------|----|----|----------|------|")

        for col in table.columns:
            pk = "O" if col.pk else ""
            fk = fk_map.get(col.name, "")
            nullable = "O" if col.nullable else "X"
            lines.append(f"| {col.name} | {col.type} | {pk} | {fk} | {nullable} | {col.comment} |")

        lines.append("")

        if table.indexes:
            lines.append("### 인덱스")
            lines.append("")
            lines.append("| 인덱스명 | 컬럼 | UNIQUE |")
            lines.append("|----------|------|--------|")
            for idx in table.indexes:
                unique = "UNIQUE" if idx.unique else ""
                cols = ", ".join(idx.columns)
                lines.append(f"| {idx.name} | {cols} | {unique} |")
            lines.append("")

    return "\n".join(lines)
```

- [ ] **Step 5: Implement api_spec params/returnType output**

`src/codemap/doc/api_spec.py` 수정 — 파라미터와 반환 타입 컬럼 추가:

```python
from codemap.models import ApiSchema


def generate_api_spec(api: ApiSchema) -> str:
    lines: list[str] = ["# API 명세서", ""]
    lines.append("| 메서드 | 경로 | 컨트롤러 | 서비스 | 파라미터 | 반환 타입 | 호출 |")
    lines.append("|--------|------|----------|--------|----------|----------|------|")

    for ep in api.endpoints:
        calls = ", ".join(ep.calls)
        params_str = ", ".join(
            f"@{p.annotation} {p.type} {p.name}" + ("?" if not p.required else "")
            for p in ep.params
        )
        lines.append(
            f"| {ep.method} | {ep.path} | {ep.controller} | {ep.service} "
            f"| {params_str} | {ep.returnType} | {calls} |"
        )

    lines.append("")
    return "\n".join(lines)
```

- [ ] **Step 6: Update xlsx export**

`src/codemap/export/xlsx.py` 수정:
- 테이블 시트: 설명 컬럼(`column 7`)에 `col.comment` 출력
- API 시트: 헤더에 "파라미터", "반환 타입" 추가

```python
# export_table_spec_xlsx — "목차" 시트의 설명 컬럼에도 table.comment 출력:
            ws_index.cell(row=ti + 1, column=3, value=table.comment)

# export_table_spec_xlsx — 테이블 시트의 빈 설명 컬럼을 comment로 교체:
            ws.cell(row=row, column=7, value=col.comment)

# export_api_spec_xlsx — 헤더와 데이터에 params/returnType 추가:
    headers = ["No", "메서드", "경로", "컨트롤러", "서비스", "파라미터", "반환 타입", "호출"]
    # ...
        params_str = ", ".join(
            f"@{p.annotation} {p.type} {p.name}" for p in ep.params
        )
        ws.cell(row=row, column=6, value=params_str)
        ws.cell(row=row, column=7, value=ep.returnType)
        ws.cell(row=row, column=8, value=", ".join(ep.calls))
```

- [ ] **Step 7: Run all affected tests**

Run: `uv run pytest tests/doc/ tests/export/ -v`
Expected: All PASS

- [ ] **Step 8: Commit**

```bash
git add src/codemap/doc/table_spec.py src/codemap/doc/api_spec.py src/codemap/export/xlsx.py tests/doc/ tests/export/
git commit -m "feat: output comment, params, returnType in doc generators and xlsx export"
```

---

## Task 5: 전체 테스트 + 실제 프로젝트 검증

**Files:**
- No new files

- [ ] **Step 1: Run full test suite**

Run: `uv run pytest tests/ -v --tb=short`
Expected: All PASS

- [ ] **Step 2: Run against iuu project to verify comments appear**

```bash
uv run codemap --verbose scan /home/ashzero/repository/iuu --target db -o /tmp/codemap-verify/scan.json
uv run python3 -c "
import json
data = json.load(open('/tmp/codemap-verify/scan.json'))
for t in data['database']['tables'][:2]:
    print(f\"Table: {t['name']} — comment: {t.get('comment', '')}\")
    for c in t['columns'][:5]:
        print(f\"  {c['name']}: {c.get('comment', '')}\")
"
```
Expected: 테이블/컬럼 comment가 한국어로 출력됨

- [ ] **Step 3: Verify API params in scan output**

```bash
uv run codemap --verbose scan /home/ashzero/repository/iuu --target api -o /tmp/codemap-verify/scan-api.json
uv run python3 -c "
import json
data = json.load(open('/tmp/codemap-verify/scan-api.json'))
for ep in data['api']['endpoints'][:5]:
    print(f\"{ep['method']} {ep['path']} params={ep.get('params', [])} return={ep.get('returnType', '')}\")
"
```
Expected: @RequestParam, @RequestBody 파라미터와 반환 타입이 출력됨

- [ ] **Step 4: Generate full docs and verify**

```bash
uv run codemap generate /home/ashzero/repository/iuu -o /tmp/codemap-verify/output --target all --format drawio --export xlsx
head -30 /tmp/codemap-verify/output/docs/table-spec.md
head -10 /tmp/codemap-verify/output/docs/api-spec.md
```
Expected: 테이블 정의서에 한국어 설명, API 명세서에 파라미터/반환 타입 표시

- [ ] **Step 5: Commit (if any fixes needed)**

```bash
git add -A
git commit -m "fix: address issues found during integration verification"
```
