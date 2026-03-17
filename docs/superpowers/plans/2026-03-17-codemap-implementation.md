# Codemap CLI Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python CLI tool (`codemap`) that statically analyzes codebases (React + Spring + Python/Shell/GDAL) and auto-generates technical documents (table specs, ERDs, sequence diagrams, architecture diagrams) in Mermaid, draw.io, PDF, Word, and Excel formats.

**Architecture:** Pipeline of subcommands (`scan → render → doc → export`) communicating via JSON intermediate data. Each subcommand is independently testable. Config loaded from `.codemap/config.yaml` with project-level overriding global.

**Tech Stack:** Python 3.12, Click (CLI), sqlglot (SQL parsing), tree-sitter (Java/TS AST), openpyxl (Excel), weasyprint (PDF, optional), python-docx (Word, optional), PyYAML (config)

**Spec:** `docs/superpowers/specs/2026-03-17-codemap-design.md`

---

## File Structure

```
codemap/
├── pyproject.toml                      # Package config, CLI entrypoint, optional deps
├── src/
│   └── codemap/
│       ├── __init__.py                 # Version constant
│       ├── cli.py                      # Click CLI groups and commands
│       ├── models.py                   # Pydantic models for scan JSON schema
│       ├── config.py                   # Config file loading and defaults
│       ├── scanner/
│       │   ├── __init__.py             # Scanner registry + run_scan()
│       │   ├── sql_scanner.py          # DDL parsing via sqlglot
│       │   ├── java_scanner.py         # Spring Controller/Service parsing via tree-sitter
│       │   ├── ts_scanner.py           # React component/API call parsing via tree-sitter
│       │   └── external_scanner.py     # External call detection (ProcessBuilder, subprocess)
│       ├── renderer/
│       │   ├── __init__.py             # Renderer registry
│       │   ├── mermaid.py              # ERD, sequence, architecture, component in Mermaid
│       │   └── drawio.py              # ERD, sequence, architecture, component in draw.io XML
│       ├── doc/
│       │   ├── __init__.py             # Doc generator registry
│       │   ├── table_spec.py           # Table definition markdown
│       │   ├── api_spec.py             # API spec markdown
│       │   └── overview.py             # Project overview markdown
│       └── export/
│           ├── __init__.py             # Export registry + optional dep checks
│           ├── xlsx.py                 # Excel export via openpyxl
│           ├── pdf.py                  # PDF export via weasyprint (optional)
│           └── docx_export.py          # Word export via python-docx (optional) — named docx_export to avoid collision with python-docx package
├── tests/
│   ├── conftest.py                     # Shared fixtures (sample SQL, Java, TS files)
│   ├── fixtures/                       # Test fixture files
│   │   ├── sample.sql                  # Sample DDL
│   │   ├── UserController.java         # Sample Spring controller
│   │   ├── UserService.java            # Sample Spring service
│   │   ├── UserList.tsx                # Sample React component
│   │   └── config.yaml                 # Sample config
│   ├── test_models.py                  # Schema model tests
│   ├── test_config.py                  # Config loading tests
│   ├── test_cli.py                     # CLI integration tests
│   ├── scanner/
│   │   ├── test_sql_scanner.py
│   │   ├── test_java_scanner.py
│   │   ├── test_ts_scanner.py
│   │   └── test_external_scanner.py
│   ├── renderer/
│   │   ├── test_mermaid.py
│   │   └── test_drawio.py
│   ├── doc/
│   │   ├── test_table_spec.py
│   │   ├── test_api_spec.py
│   │   └── test_overview.py
│   └── export/
│       ├── test_xlsx.py
│       ├── test_pdf.py
│       └── test_docx_export.py
└── .codemap/
    └── templates/
        └── minimal.css                 # Default PDF template
```

---

## Task 1: Project Scaffolding + Data Models

**Files:**
- Create: `pyproject.toml`
- Create: `src/codemap/__init__.py`
- Create: `src/codemap/models.py`
- Create: `tests/conftest.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: Create pyproject.toml**

```toml
[build-system]
requires = ["setuptools>=68.0", "setuptools-scm"]
build-backend = "setuptools.backends._legacy:_Backend"

[project]
name = "codemap"
version = "0.1.0"
description = "Codebase analysis and technical document auto-generation CLI"
requires-python = ">=3.12"
dependencies = [
    "click>=8.1",
    "sqlglot>=23.0",
    "tree-sitter>=0.21",
    "tree-sitter-java>=0.21",
    "tree-sitter-typescript>=0.21",
    "openpyxl>=3.1",
    "pyyaml>=6.0",
    "pydantic>=2.0",
    "markdown>=3.5",
]

[project.optional-dependencies]
pdf = ["weasyprint>=60.0"]
docx = ["python-docx>=1.0"]
all = ["codemap[pdf]", "codemap[docx]"]

[project.scripts]
codemap = "codemap.cli:main"

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]

[tool.setuptools.packages.find]
where = ["src"]
```

- [ ] **Step 2: Create `src/codemap/__init__.py`**

```python
__version__ = "0.1.0"
```

- [ ] **Step 3: Write failing test for data models**

```python
# tests/test_models.py
from codemap.models import (
    ScanResult,
    Table,
    Column,
    ForeignKey,
    Index,
    Endpoint,
    Module,
    ExternalCall,
    Component,
    ApiCall,
)


def test_scan_result_empty():
    result = ScanResult(project="test")
    assert result.version == "1.0"
    assert result.project == "test"
    assert result.database.tables == []
    assert result.api.endpoints == []
    assert result.dependencies.modules == []
    assert result.frontend.components == []


def test_table_with_columns():
    col = Column(name="id", type="BIGINT", pk=True, nullable=False)
    fk = ForeignKey(column="dept_id", references="departments.id")
    idx = Index(name="idx_email", columns=["email"], unique=True)
    table = Table(name="users", columns=[col], foreignKeys=[fk], indexes=[idx])
    assert table.name == "users"
    assert table.columns[0].pk is True
    assert table.foreignKeys[0].references == "departments.id"


def test_endpoint():
    ep = Endpoint(
        method="POST",
        path="/api/users",
        controller="UserController",
        service="UserService",
        calls=["UserRepository.save"],
    )
    assert ep.method == "POST"
    assert ep.controller == "UserController"


def test_module():
    mod = Module(
        name="UserService",
        type="service",
        file="src/main/java/UserService.java",
        dependsOn=["UserRepository"],
        layer="service",
    )
    assert mod.layer == "service"


def test_external_call():
    ec = ExternalCall(
        source="GdalService.convert",
        type="process",
        command="gdal_translate",
        file="GdalService.java",
        line=42,
    )
    assert ec.type == "process"


def test_component():
    comp = Component(
        name="UserList",
        file="UserList.tsx",
        children=["UserCard"],
        hooks=["useState"],
    )
    assert comp.children == ["UserCard"]


def test_api_call():
    ac = ApiCall(
        component="UserList",
        method="GET",
        path="/api/users",
        file="UserList.tsx",
        line=15,
    )
    assert ac.method == "GET"


def test_scan_result_to_json():
    result = ScanResult(project="test")
    data = result.model_dump()
    assert data["version"] == "1.0"
    assert "database" in data
    assert "api" in data
    assert "scannedAt" in data
```

- [ ] **Step 4: Run test to verify it fails**

Run: `cd /home/ashzero/repository/ai-project && python3 -m pytest tests/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'codemap.models'`

- [ ] **Step 5: Implement data models**

```python
# src/codemap/models.py
from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field


class Column(BaseModel):
    name: str
    type: str
    pk: bool = False
    nullable: bool = True


class ForeignKey(BaseModel):
    column: str
    references: str


class Index(BaseModel):
    name: str
    columns: list[str]
    unique: bool = False


class Table(BaseModel):
    name: str
    columns: list[Column] = Field(default_factory=list)
    foreignKeys: list[ForeignKey] = Field(default_factory=list)
    indexes: list[Index] = Field(default_factory=list)


class DatabaseSchema(BaseModel):
    tables: list[Table] = Field(default_factory=list)


class Endpoint(BaseModel):
    method: str
    path: str
    controller: str
    service: str
    calls: list[str] = Field(default_factory=list)


class ApiSchema(BaseModel):
    endpoints: list[Endpoint] = Field(default_factory=list)


class Module(BaseModel):
    name: str
    type: str
    file: str
    dependsOn: list[str] = Field(default_factory=list)
    layer: str


class ExternalCall(BaseModel):
    source: str = Field(alias="from", serialization_alias="from")
    type: str
    command: str
    file: str
    line: int

    model_config = {"populate_by_name": True}


class DependencySchema(BaseModel):
    modules: list[Module] = Field(default_factory=list)
    externalCalls: list[ExternalCall] = Field(default_factory=list)


class Component(BaseModel):
    name: str
    file: str
    children: list[str] = Field(default_factory=list)
    hooks: list[str] = Field(default_factory=list)


class ApiCall(BaseModel):
    component: str
    method: str
    path: str
    file: str
    line: int


class FrontendSchema(BaseModel):
    components: list[Component] = Field(default_factory=list)
    apiCalls: list[ApiCall] = Field(default_factory=list)


class ScanResult(BaseModel):
    version: str = "1.0"
    project: str
    scannedAt: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    database: DatabaseSchema = Field(default_factory=DatabaseSchema)
    api: ApiSchema = Field(default_factory=ApiSchema)
    dependencies: DependencySchema = Field(default_factory=DependencySchema)
    frontend: FrontendSchema = Field(default_factory=FrontendSchema)
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd /home/ashzero/repository/ai-project && pip install -e ".[all]" && python3 -m pytest tests/test_models.py -v`
Expected: All PASS

- [ ] **Step 7: Create `tests/conftest.py`**

```python
# tests/conftest.py
from pathlib import Path

import pytest

FIXTURE_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixture_dir():
    return FIXTURE_DIR


@pytest.fixture
def sample_sql():
    return FIXTURE_DIR / "sample.sql"
```

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml src/ tests/
git commit -m "feat: scaffold project and implement scan data models"
```

---

## Task 2: Config System

**Files:**
- Create: `src/codemap/config.py`
- Create: `tests/test_config.py`
- Create: `tests/fixtures/config.yaml`

- [ ] **Step 1: Create test fixture config**

```yaml
# tests/fixtures/config.yaml
project:
  name: "test-project"
  description: "Test project"

scan:
  database:
    paths: ["doc/database/**/*.sql"]
  backend:
    paths: ["src/main/java/**/*.java"]
    framework: spring
  frontend:
    paths: ["src/frontend/**/*.{ts,tsx}"]
    framework: react
  external:
    patterns:
      - type: process
        keywords: ["ProcessBuilder", "Runtime.exec"]

export:
  template: "minimal"
```

- [ ] **Step 2: Write failing test**

```python
# tests/test_config.py
import os
from pathlib import Path

from codemap.config import load_config, CodemapConfig, DEFAULT_CONFIG


def test_default_config():
    cfg = DEFAULT_CONFIG
    assert cfg.project.name == ""
    assert cfg.scan.database.paths == ["doc/database/**/*.sql"]
    assert cfg.scan.backend.framework == "spring"


def test_load_config_from_file(tmp_path):
    config_dir = tmp_path / ".codemap"
    config_dir.mkdir()
    config_file = config_dir / "config.yaml"
    config_file.write_text(
        "project:\n  name: my-proj\nscan:\n  database:\n    paths: ['db/*.sql']\n"
    )
    cfg = load_config(tmp_path)
    assert cfg.project.name == "my-proj"
    assert cfg.scan.database.paths == ["db/*.sql"]
    # Non-overridden fields keep defaults
    assert cfg.scan.backend.framework == "spring"


def test_load_config_missing_file(tmp_path):
    cfg = load_config(tmp_path)
    assert cfg.project.name == ""
    assert cfg.scan.database.paths == ["doc/database/**/*.sql"]


def test_load_config_from_fixture():
    fixture_dir = Path(__file__).parent / "fixtures"
    # Create a temporary project dir pointing to fixture config
    cfg = load_config(fixture_dir, config_filename="config.yaml")
    assert cfg.project.name == "test-project"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python3 -m pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'codemap.config'`

- [ ] **Step 4: Implement config**

```python
# src/codemap/config.py
from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class ProjectConfig(BaseModel):
    name: str = ""
    description: str = ""


class DatabaseScanConfig(BaseModel):
    paths: list[str] = Field(default_factory=lambda: ["doc/database/**/*.sql"])


class BackendScanConfig(BaseModel):
    paths: list[str] = Field(default_factory=lambda: ["src/main/java/**/*.java"])
    framework: str = "spring"


class FrontendScanConfig(BaseModel):
    paths: list[str] = Field(default_factory=lambda: ["src/frontend/**/*.{ts,tsx}"])
    framework: str = "react"


class ExternalPattern(BaseModel):
    type: str
    keywords: list[str]


class ExternalScanConfig(BaseModel):
    patterns: list[ExternalPattern] = Field(
        default_factory=lambda: [
            ExternalPattern(type="process", keywords=["ProcessBuilder", "Runtime.exec"]),
            ExternalPattern(type="python", keywords=["python", "python3"]),
            ExternalPattern(type="gdal", keywords=["gdal_translate", "ogr2ogr"]),
        ]
    )


class ScanConfig(BaseModel):
    database: DatabaseScanConfig = Field(default_factory=DatabaseScanConfig)
    backend: BackendScanConfig = Field(default_factory=BackendScanConfig)
    frontend: FrontendScanConfig = Field(default_factory=FrontendScanConfig)
    external: ExternalScanConfig = Field(default_factory=ExternalScanConfig)


class ExportConfig(BaseModel):
    template: str = "minimal"
    logo: str = ""


class CodemapConfig(BaseModel):
    project: ProjectConfig = Field(default_factory=ProjectConfig)
    scan: ScanConfig = Field(default_factory=ScanConfig)
    export: ExportConfig = Field(default_factory=ExportConfig)


DEFAULT_CONFIG = CodemapConfig()


def _deep_merge(base: dict, override: dict) -> dict:
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(
    project_path: Path,
    config_filename: str = ".codemap/config.yaml",
) -> CodemapConfig:
    config_file = project_path / config_filename
    global_config_file = Path.home() / ".codemap" / "config.yaml"

    base_data: dict = {}
    if global_config_file.exists():
        with open(global_config_file) as f:
            base_data = yaml.safe_load(f) or {}

    if config_file.exists():
        with open(config_file) as f:
            project_data = yaml.safe_load(f) or {}
        base_data = _deep_merge(base_data, project_data)

    if not base_data:
        return DEFAULT_CONFIG

    return CodemapConfig(**base_data)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python3 -m pytest tests/test_config.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add src/codemap/config.py tests/test_config.py tests/fixtures/config.yaml
git commit -m "feat: implement config system with YAML loading and defaults"
```

---

## Task 3: SQL Scanner

**Files:**
- Create: `src/codemap/scanner/__init__.py`
- Create: `src/codemap/scanner/sql_scanner.py`
- Create: `tests/fixtures/sample.sql`
- Create: `tests/scanner/test_sql_scanner.py`

- [ ] **Step 1: Create SQL fixture**

```sql
-- tests/fixtures/sample.sql
CREATE TABLE departments (
    id BIGINT PRIMARY KEY,
    name VARCHAR(255) NOT NULL
);

CREATE TABLE users (
    id BIGINT PRIMARY KEY,
    email VARCHAR(255) NOT NULL,
    dept_id BIGINT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_users_dept FOREIGN KEY (dept_id) REFERENCES departments(id)
);

CREATE UNIQUE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_dept ON users(dept_id);
```

- [ ] **Step 2: Write failing test**

```python
# tests/scanner/test_sql_scanner.py
from pathlib import Path

from codemap.scanner.sql_scanner import scan_sql


FIXTURE_DIR = Path(__file__).parent.parent / "fixtures"


def test_scan_sql_tables():
    tables = scan_sql([FIXTURE_DIR / "sample.sql"])
    assert len(tables) == 2
    names = {t.name for t in tables}
    assert "users" in names
    assert "departments" in names


def test_scan_sql_columns():
    tables = scan_sql([FIXTURE_DIR / "sample.sql"])
    users = next(t for t in tables if t.name == "users")
    assert len(users.columns) == 4
    id_col = next(c for c in users.columns if c.name == "id")
    assert id_col.pk is True
    email_col = next(c for c in users.columns if c.name == "email")
    assert email_col.nullable is False


def test_scan_sql_foreign_keys():
    tables = scan_sql([FIXTURE_DIR / "sample.sql"])
    users = next(t for t in tables if t.name == "users")
    assert len(users.foreignKeys) == 1
    assert users.foreignKeys[0].column == "dept_id"
    assert users.foreignKeys[0].references == "departments.id"


def test_scan_sql_indexes():
    tables = scan_sql([FIXTURE_DIR / "sample.sql"])
    users = next(t for t in tables if t.name == "users")
    assert len(users.indexes) >= 1
    email_idx = next(i for i in users.indexes if i.name == "idx_users_email")
    assert email_idx.unique is True
    assert "email" in email_idx.columns


def test_scan_sql_invalid_file(tmp_path):
    bad_file = tmp_path / "bad.sql"
    bad_file.write_text("THIS IS NOT SQL AT ALL!!!")
    tables = scan_sql([bad_file])
    assert tables == []  # Graceful skip


def test_scan_sql_empty_list():
    tables = scan_sql([])
    assert tables == []
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python3 -m pytest tests/scanner/test_sql_scanner.py -v`
Expected: FAIL

- [ ] **Step 4: Implement SQL scanner**

```python
# src/codemap/scanner/__init__.py
```

```python
# src/codemap/scanner/sql_scanner.py
from __future__ import annotations

import logging
from pathlib import Path

import sqlglot
from sqlglot import exp

from codemap.models import Table, Column, ForeignKey, Index

logger = logging.getLogger(__name__)


def scan_sql(sql_files: list[Path]) -> list[Table]:
    tables: list[Table] = []
    indexes: dict[str, list[Index]] = {}

    for sql_file in sql_files:
        try:
            sql_text = sql_file.read_text(encoding="utf-8")
            statements = sqlglot.parse(sql_text)
        except Exception as e:
            logger.warning(f"Failed to parse {sql_file}: {e}")
            continue

        for stmt in statements:
            if stmt is None:
                continue
            if isinstance(stmt, exp.Create):
                table = _parse_create_table(stmt)
                if table:
                    tables.append(table)
            elif isinstance(stmt, exp.Command) or _is_create_index(stmt):
                idx = _parse_create_index(stmt, sql_text)
                if idx:
                    table_name, index = idx
                    indexes.setdefault(table_name, []).append(index)

    # Attach indexes to tables
    for table in tables:
        if table.name in indexes:
            table.indexes.extend(indexes[table.name])

    return tables


def _is_create_index(stmt) -> bool:
    return isinstance(stmt, exp.Create) and stmt.kind == "INDEX"


def _parse_create_table(stmt: exp.Create) -> Table | None:
    if stmt.kind != "TABLE":
        return None

    table_name_expr = stmt.this
    if not isinstance(table_name_expr, exp.Schema):
        return None

    table_name = table_name_expr.this.name if table_name_expr.this else None
    if not table_name:
        return None

    columns: list[Column] = []
    foreign_keys: list[ForeignKey] = []

    # Find primary key columns from constraints
    pk_columns: set[str] = set()
    for col_def in table_name_expr.expressions:
        if isinstance(col_def, exp.ColumnDef):
            for constraint in col_def.find_all(exp.PrimaryKeyColumnConstraint):
                pk_columns.add(col_def.name)
        elif isinstance(col_def, exp.PrimaryKey):
            for expr in col_def.expressions:
                if hasattr(expr, "name"):
                    pk_columns.add(expr.name)

    # Parse columns
    for col_def in table_name_expr.expressions:
        if isinstance(col_def, exp.ColumnDef):
            col_name = col_def.name
            col_type = col_def.args.get("kind")
            type_str = col_type.sql() if col_type else "UNKNOWN"

            nullable = True
            for constraint in col_def.find_all(exp.NotNullColumnConstraint):
                nullable = False

            is_pk = col_name in pk_columns
            if is_pk:
                nullable = False

            columns.append(Column(name=col_name, type=type_str, pk=is_pk, nullable=nullable))

        # Foreign key constraints
        elif isinstance(col_def, exp.ForeignKey):
            fk_cols = [e.name for e in col_def.expressions if hasattr(e, "name")]
            ref = col_def.find(exp.Reference)
            if ref and fk_cols:
                ref_table = ref.this.name if ref.this else ""
                ref_cols = [e.name for e in ref.expressions if hasattr(e, "name")]
                for fc, rc in zip(fk_cols, ref_cols if ref_cols else [""]):
                    foreign_keys.append(
                        ForeignKey(column=fc, references=f"{ref_table}.{rc}" if rc else ref_table)
                    )

    return Table(name=table_name, columns=columns, foreignKeys=foreign_keys)


def _parse_create_index(stmt, sql_text: str) -> tuple[str, Index] | None:
    try:
        if isinstance(stmt, exp.Create) and stmt.kind == "INDEX":
            index_name = ""
            unique = False

            # Check for UNIQUE
            props = stmt.args.get("properties")
            if "UNIQUE" in stmt.sql().upper().split("INDEX")[0]:
                unique = True

            # Get index name
            idx_expr = stmt.this
            if hasattr(idx_expr, "this") and hasattr(idx_expr.this, "name"):
                index_name = idx_expr.this.name

            # Get table name
            table_expr = stmt.find(exp.Table)
            if not table_expr:
                return None
            table_name = table_expr.name

            # Get columns
            cols = []
            for col in idx_expr.expressions if hasattr(idx_expr, "expressions") else []:
                if hasattr(col, "name"):
                    cols.append(col.name)

            if index_name and table_name and cols:
                return table_name, Index(name=index_name, columns=cols, unique=unique)
    except Exception as e:
        logger.warning(f"Failed to parse index: {e}")

    return None
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python3 -m pytest tests/scanner/test_sql_scanner.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add src/codemap/scanner/ tests/scanner/ tests/fixtures/sample.sql
git commit -m "feat: implement SQL scanner with DDL parsing via sqlglot"
```

---

## Task 4: Java Scanner (Spring Controller/Service)

**Files:**
- Create: `src/codemap/scanner/java_scanner.py`
- Create: `tests/fixtures/UserController.java`
- Create: `tests/fixtures/UserService.java`
- Create: `tests/scanner/test_java_scanner.py`

- [ ] **Step 1: Create Java fixtures**

```java
// tests/fixtures/UserController.java
package com.example.user;

import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/users")
public class UserController {

    private final UserService userService;

    public UserController(UserService userService) {
        this.userService = userService;
    }

    @GetMapping
    public List<User> getUsers() {
        return userService.findAll();
    }

    @PostMapping
    public User createUser(@RequestBody User user) {
        return userService.create(user);
    }

    @GetMapping("/{id}")
    public User getUser(@PathVariable Long id) {
        return userService.findById(id);
    }
}
```

```java
// tests/fixtures/UserService.java
package com.example.user;

import org.springframework.stereotype.Service;

@Service
public class UserService {

    private final UserRepository userRepository;
    private final EmailService emailService;

    public UserService(UserRepository userRepository, EmailService emailService) {
        this.userRepository = userRepository;
        this.emailService = emailService;
    }

    public List<User> findAll() {
        return userRepository.findAll();
    }

    public User create(User user) {
        User saved = userRepository.save(user);
        emailService.sendWelcome(saved);
        return saved;
    }

    public User findById(Long id) {
        return userRepository.findById(id);
    }
}
```

- [ ] **Step 2: Write failing test**

```python
# tests/scanner/test_java_scanner.py
from pathlib import Path

from codemap.scanner.java_scanner import scan_java
from codemap.models import Endpoint, Module

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures"


def test_scan_java_endpoints():
    endpoints, modules = scan_java(
        [FIXTURE_DIR / "UserController.java", FIXTURE_DIR / "UserService.java"]
    )
    assert len(endpoints) >= 3
    paths = {ep.path for ep in endpoints}
    assert "/api/users" in paths or any("/api/users" in p for p in paths)


def test_scan_java_endpoint_details():
    endpoints, _ = scan_java(
        [FIXTURE_DIR / "UserController.java", FIXTURE_DIR / "UserService.java"]
    )
    get_all = next((ep for ep in endpoints if ep.method == "GET" and ep.path == "/api/users"), None)
    assert get_all is not None
    assert get_all.controller == "UserController"
    assert get_all.service == "UserService"


def test_scan_java_modules():
    _, modules = scan_java(
        [FIXTURE_DIR / "UserController.java", FIXTURE_DIR / "UserService.java"]
    )
    service_mod = next((m for m in modules if m.name == "UserService"), None)
    assert service_mod is not None
    assert "UserRepository" in service_mod.dependsOn
    assert "EmailService" in service_mod.dependsOn
    assert service_mod.layer == "service"


def test_scan_java_controller_module():
    _, modules = scan_java(
        [FIXTURE_DIR / "UserController.java", FIXTURE_DIR / "UserService.java"]
    )
    ctrl_mod = next((m for m in modules if m.name == "UserController"), None)
    assert ctrl_mod is not None
    assert ctrl_mod.layer == "controller"
    assert "UserService" in ctrl_mod.dependsOn


def test_scan_java_empty():
    endpoints, modules = scan_java([])
    assert endpoints == []
    assert modules == []
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python3 -m pytest tests/scanner/test_java_scanner.py -v`
Expected: FAIL

- [ ] **Step 4: Implement Java scanner**

Use tree-sitter-java to parse Java AST. Extract `@RestController` classes, `@RequestMapping`/`@GetMapping`/`@PostMapping` methods for endpoints. Extract constructor injection for dependency detection. Classify by annotation: `@Controller`/`@RestController` → controller layer, `@Service` → service layer, `@Repository` → repository layer.

Key implementation:
- Parse class-level `@RequestMapping` for base path
- Parse method-level `@GetMapping`, `@PostMapping`, `@PutMapping`, `@DeleteMapping`, `@PatchMapping` for sub-path and HTTP method
- Combine base path + sub-path
- Extract constructor parameters as dependencies
- Match controller → service via injected field type names

*(Implementation in `src/codemap/scanner/java_scanner.py` — tree-sitter AST walking with annotation-based extraction)*

- [ ] **Step 5: Run test to verify it passes**

Run: `python3 -m pytest tests/scanner/test_java_scanner.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add src/codemap/scanner/java_scanner.py tests/scanner/test_java_scanner.py tests/fixtures/UserController.java tests/fixtures/UserService.java
git commit -m "feat: implement Java scanner for Spring Controller/Service analysis"
```

---

## Task 5: TypeScript Scanner (React Components)

**Files:**
- Create: `src/codemap/scanner/ts_scanner.py`
- Create: `tests/fixtures/UserList.tsx`
- Create: `tests/scanner/test_ts_scanner.py`

- [ ] **Step 1: Create TSX fixture**

```tsx
// tests/fixtures/UserList.tsx
import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { UserCard } from './UserCard';
import { Pagination } from './Pagination';

export const UserList: React.FC = () => {
    const [users, setUsers] = useState([]);
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        const fetchUsers = async () => {
            setLoading(true);
            const response = await axios.get('/api/users');
            setUsers(response.data);
            setLoading(false);
        };
        fetchUsers();
    }, []);

    const handleDelete = async (id: number) => {
        await axios.delete(`/api/users/${id}`);
    };

    return (
        <div>
            {users.map(user => <UserCard key={user.id} user={user} />)}
            <Pagination />
        </div>
    );
};
```

- [ ] **Step 2: Write failing test**

```python
# tests/scanner/test_ts_scanner.py
from pathlib import Path

from codemap.scanner.ts_scanner import scan_typescript
from codemap.models import Component, ApiCall

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures"


def test_scan_ts_components():
    components, api_calls = scan_typescript([FIXTURE_DIR / "UserList.tsx"])
    assert len(components) >= 1
    user_list = next((c for c in components if c.name == "UserList"), None)
    assert user_list is not None
    assert "UserCard" in user_list.children
    assert "Pagination" in user_list.children


def test_scan_ts_hooks():
    components, _ = scan_typescript([FIXTURE_DIR / "UserList.tsx"])
    user_list = next(c for c in components if c.name == "UserList")
    assert "useState" in user_list.hooks
    assert "useEffect" in user_list.hooks


def test_scan_ts_api_calls():
    _, api_calls = scan_typescript([FIXTURE_DIR / "UserList.tsx"])
    assert len(api_calls) >= 1
    get_call = next((a for a in api_calls if a.method == "GET"), None)
    assert get_call is not None
    assert get_call.path == "/api/users"
    assert get_call.component == "UserList"


def test_scan_ts_empty():
    components, api_calls = scan_typescript([])
    assert components == []
    assert api_calls == []
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python3 -m pytest tests/scanner/test_ts_scanner.py -v`
Expected: FAIL

- [ ] **Step 4: Implement TypeScript scanner**

Use tree-sitter-typescript to parse TSX. Extract:
- Component declarations (function components, arrow function exports)
- JSX children component references
- Hook calls (`useState`, `useEffect`, etc.)
- `axios.get/post/put/delete` and `fetch()` calls for API call detection

*(Implementation in `src/codemap/scanner/ts_scanner.py`)*

- [ ] **Step 5: Run test to verify it passes**

Run: `python3 -m pytest tests/scanner/test_ts_scanner.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add src/codemap/scanner/ts_scanner.py tests/scanner/test_ts_scanner.py tests/fixtures/UserList.tsx
git commit -m "feat: implement TypeScript scanner for React component analysis"
```

---

## Task 6: External Call Scanner

**Files:**
- Create: `src/codemap/scanner/external_scanner.py`
- Create: `tests/fixtures/GdalService.java`
- Create: `tests/scanner/test_external_scanner.py`

- [ ] **Step 1: Create fixture**

```java
// tests/fixtures/GdalService.java
package com.example.gdal;

import java.io.IOException;

@Service
public class GdalService {

    public void convert(String input, String output) throws IOException {
        ProcessBuilder pb = new ProcessBuilder(
            "gdal_translate", "-of", "GTiff", input, output
        );
        pb.start().waitFor();
    }

    public void runPython(String script) throws IOException {
        Runtime.getRuntime().exec(new String[]{"python3", script});
    }

    public void runShell(String command) throws IOException {
        ProcessBuilder pb = new ProcessBuilder("/bin/bash", "-c", command);
        pb.start();
    }
}
```

- [ ] **Step 2: Write failing test**

```python
# tests/scanner/test_external_scanner.py
from pathlib import Path

from codemap.scanner.external_scanner import scan_external_calls
from codemap.config import DEFAULT_CONFIG

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures"


def test_scan_external_calls():
    calls = scan_external_calls(
        [FIXTURE_DIR / "GdalService.java"],
        DEFAULT_CONFIG.scan.external.patterns,
    )
    assert len(calls) >= 2


def test_scan_external_gdal():
    calls = scan_external_calls(
        [FIXTURE_DIR / "GdalService.java"],
        DEFAULT_CONFIG.scan.external.patterns,
    )
    gdal_calls = [c for c in calls if c.type == "gdal" or "gdal_translate" in c.command]
    assert len(gdal_calls) >= 1
    assert gdal_calls[0].source.endswith(".convert") or "GdalService" in gdal_calls[0].source


def test_scan_external_python():
    calls = scan_external_calls(
        [FIXTURE_DIR / "GdalService.java"],
        DEFAULT_CONFIG.scan.external.patterns,
    )
    python_calls = [c for c in calls if c.type == "python" or "python" in c.command]
    assert len(python_calls) >= 1


def test_scan_external_empty():
    calls = scan_external_calls([], DEFAULT_CONFIG.scan.external.patterns)
    assert calls == []
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python3 -m pytest tests/scanner/test_external_scanner.py -v`
Expected: FAIL

- [ ] **Step 4: Implement external call scanner**

Scan Java files for `ProcessBuilder` and `Runtime.exec` patterns using tree-sitter AST. Match command strings against configured external patterns (process, python, gdal) to classify call types.

*(Implementation in `src/codemap/scanner/external_scanner.py`)*

- [ ] **Step 5: Run test to verify it passes**

Run: `python3 -m pytest tests/scanner/test_external_scanner.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add src/codemap/scanner/external_scanner.py tests/scanner/test_external_scanner.py tests/fixtures/GdalService.java
git commit -m "feat: implement external call scanner for ProcessBuilder/Runtime.exec detection"
```

---

## Task 7: CLI Skeleton + `scan` Command

**Files:**
- Create: `src/codemap/cli.py`
- Create: `tests/test_cli.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_cli.py
import json
from pathlib import Path

from click.testing import CliRunner

from codemap.cli import main

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def test_cli_scan_outputs_json(tmp_path):
    output_file = tmp_path / "scan.json"
    runner = CliRunner()
    result = runner.invoke(main, ["scan", str(FIXTURE_DIR), "-o", str(output_file), "--target", "db"])
    assert result.exit_code == 0
    assert output_file.exists()
    data = json.loads(output_file.read_text())
    assert data["version"] == "1.0"
    assert "database" in data


def test_cli_scan_target_db(tmp_path):
    output_file = tmp_path / "scan.json"
    runner = CliRunner()
    result = runner.invoke(main, ["scan", str(FIXTURE_DIR), "-o", str(output_file), "--target", "db"])
    assert result.exit_code == 0
    data = json.loads(output_file.read_text())
    assert len(data["database"]["tables"]) > 0


def test_cli_scan_stdout():
    runner = CliRunner()
    result = runner.invoke(main, ["scan", str(FIXTURE_DIR), "--target", "db"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "database" in data


def test_cli_version():
    runner = CliRunner()
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.output
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_cli.py -v`
Expected: FAIL

- [ ] **Step 3: Implement CLI**

```python
# src/codemap/cli.py
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import click

from codemap import __version__
from codemap.config import load_config
from codemap.models import ScanResult


@click.group()
@click.version_option(version=__version__)
@click.option("-v", "--verbose", is_flag=True, help="Verbose output")
@click.option("-q", "--quiet", is_flag=True, help="Quiet output")
@click.option("--debug", is_flag=True, help="Debug output")
@click.pass_context
def main(ctx, verbose, quiet, debug):
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

    json_str = json.dumps(result.model_dump(), indent=2, ensure_ascii=False)
    if output:
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).write_text(json_str, encoding="utf-8")
        if not ctx.obj.get("quiet"):
            click.echo(f"Scan result saved to {output}", err=True)
    else:
        click.echo(json_str)
```

```python
# src/codemap/scanner/__init__.py (update)
from __future__ import annotations

import logging
from pathlib import Path

from codemap.config import CodemapConfig
from codemap.models import ScanResult, DatabaseSchema, ApiSchema, DependencySchema, FrontendSchema

logger = logging.getLogger(__name__)


def _glob_files(project_path: Path, patterns: list[str]) -> list[Path]:
    files = []
    for pattern in patterns:
        files.extend(sorted(project_path.glob(pattern)))
    return files


def run_scan(project_path: Path, config: CodemapConfig, targets: set[str]) -> ScanResult:
    scan_all = "all" in targets
    result = ScanResult(project=config.project.name or project_path.name)

    if scan_all or "db" in targets:
        from codemap.scanner.sql_scanner import scan_sql
        sql_files = _glob_files(project_path, config.scan.database.paths)
        tables = scan_sql(sql_files)
        result.database = DatabaseSchema(tables=tables)
        logger.info(f"Scanned {len(sql_files)} SQL files, found {len(tables)} tables")

    if scan_all or "api" in targets or "deps" in targets:
        from codemap.scanner.java_scanner import scan_java
        java_files = _glob_files(project_path, config.scan.backend.paths)
        endpoints, modules = scan_java(java_files)
        if scan_all or "api" in targets:
            result.api = ApiSchema(endpoints=endpoints)
        if scan_all or "deps" in targets:
            result.dependencies.modules = modules
        logger.info(f"Scanned {len(java_files)} Java files")

    if scan_all or "deps" in targets:
        from codemap.scanner.external_scanner import scan_external_calls
        java_files = _glob_files(project_path, config.scan.backend.paths)
        external_calls = scan_external_calls(java_files, config.scan.external.patterns)
        result.dependencies.externalCalls = external_calls

    if scan_all or "frontend" in targets:
        from codemap.scanner.ts_scanner import scan_typescript
        ts_files = _glob_files(project_path, config.scan.frontend.paths)
        components, api_calls = scan_typescript(ts_files)
        result.frontend = FrontendSchema(components=components, apiCalls=api_calls)
        logger.info(f"Scanned {len(ts_files)} TS/TSX files")

    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_cli.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/codemap/cli.py src/codemap/scanner/__init__.py tests/test_cli.py
git commit -m "feat: implement CLI skeleton with scan command"
```

---

## Task 8: Mermaid Renderer

**Files:**
- Create: `src/codemap/renderer/__init__.py`
- Create: `src/codemap/renderer/mermaid.py`
- Create: `tests/renderer/test_mermaid.py`

- [ ] **Step 1: Write failing test**

```python
# tests/renderer/test_mermaid.py
from codemap.models import (
    ScanResult, DatabaseSchema, Table, Column, ForeignKey,
    ApiSchema, Endpoint, DependencySchema, Module, ExternalCall,
)
from codemap.renderer.mermaid import render_erd, render_sequence, render_architecture, render_component


def _sample_db():
    return DatabaseSchema(tables=[
        Table(name="users", columns=[
            Column(name="id", type="BIGINT", pk=True, nullable=False),
            Column(name="email", type="VARCHAR(255)", nullable=False),
            Column(name="dept_id", type="BIGINT"),
        ], foreignKeys=[ForeignKey(column="dept_id", references="departments.id")]),
        Table(name="departments", columns=[
            Column(name="id", type="BIGINT", pk=True, nullable=False),
            Column(name="name", type="VARCHAR(255)", nullable=False),
        ]),
    ])


def test_render_erd_mermaid():
    result = render_erd(_sample_db())
    assert "erDiagram" in result
    assert "USERS" in result
    assert "DEPARTMENTS" in result
    assert "BIGINT id PK" in result


def test_render_erd_relationships():
    result = render_erd(_sample_db())
    assert "USERS" in result and "DEPARTMENTS" in result
    # Should contain a relationship line
    assert "}o--||" in result or "||--o{" in result or "--" in result


def test_render_sequence():
    endpoints = [
        Endpoint(method="POST", path="/api/users", controller="UserController",
                 service="UserService", calls=["UserRepository.save", "EmailService.send"]),
    ]
    entries = ["UserController.createUser", "UserService.create", "UserRepository.save"]
    result = render_sequence(
        ApiSchema(endpoints=endpoints),
        DependencySchema(),
        entries=["UserController", "UserService", "UserRepository.save", "EmailService.send"],
        label="사용자 생성",
    )
    assert "sequenceDiagram" in result
    assert "사용자 생성" in result


def test_render_architecture():
    scan = ScanResult(project="test")
    scan.database = _sample_db()
    scan.api = ApiSchema(endpoints=[
        Endpoint(method="GET", path="/api/users", controller="UserController",
                 service="UserService", calls=["UserRepository.findAll"]),
    ])
    scan.dependencies = DependencySchema(modules=[
        Module(name="UserService", type="service", file="UserService.java",
               dependsOn=["UserRepository"], layer="service"),
    ], externalCalls=[
        ExternalCall(source="GdalService.convert", type="process",
                     command="gdal_translate", file="GdalService.java", line=42),
    ])
    result = render_architecture(scan)
    assert "graph" in result or "flowchart" in result
    assert "Frontend" in result or "Backend" in result or "Database" in result


def test_render_component():
    deps = DependencySchema(modules=[
        Module(name="UserService", type="service", file="a.java",
               dependsOn=["UserRepository", "EmailService"], layer="service"),
        Module(name="UserRepository", type="repository", file="b.java",
               dependsOn=[], layer="repository"),
    ])
    result = render_component(deps)
    assert "graph" in result or "flowchart" in result
    assert "UserService" in result
    assert "UserRepository" in result


def test_render_erd_empty():
    result = render_erd(DatabaseSchema())
    assert "erDiagram" in result  # Valid but empty diagram
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/renderer/test_mermaid.py -v`
Expected: FAIL

- [ ] **Step 3: Implement Mermaid renderer**

Implement `render_erd`, `render_sequence`, `render_architecture`, `render_component` functions that produce Mermaid syntax strings.

- `render_erd`: erDiagram with table entities and relationship lines
- `render_sequence`: sequenceDiagram with participant → message arrows from endpoint call chains
- `render_architecture`: flowchart TD with subgraph layers (Frontend, Backend, Database, External)
- `render_component`: flowchart TD with module nodes and dependency arrows

*(Implementation in `src/codemap/renderer/mermaid.py`)*

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/renderer/test_mermaid.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/codemap/renderer/ tests/renderer/
git commit -m "feat: implement Mermaid renderer for ERD, sequence, architecture, component diagrams"
```

---

## Task 9: draw.io Renderer

**Files:**
- Create: `src/codemap/renderer/drawio.py`
- Create: `tests/renderer/test_drawio.py`

- [ ] **Step 1: Write failing test**

```python
# tests/renderer/test_drawio.py
import xml.etree.ElementTree as ET

from codemap.models import DatabaseSchema, Table, Column, ForeignKey, DependencySchema, Module
from codemap.renderer.drawio import (
    render_erd_drawio, render_sequence_drawio,
    render_architecture_drawio, render_component_drawio,
)
from codemap.models import (
    DatabaseSchema, Table, Column, ForeignKey, DependencySchema, Module,
    ScanResult, ApiSchema, Endpoint, ExternalCall,
)


def _sample_db():
    return DatabaseSchema(tables=[
        Table(name="users", columns=[
            Column(name="id", type="BIGINT", pk=True, nullable=False),
            Column(name="email", type="VARCHAR(255)"),
        ], foreignKeys=[ForeignKey(column="dept_id", references="departments.id")]),
        Table(name="departments", columns=[
            Column(name="id", type="BIGINT", pk=True, nullable=False),
            Column(name="name", type="VARCHAR(255)"),
        ]),
    ])


def test_drawio_erd_valid_xml():
    result = render_erd_drawio(_sample_db())
    root = ET.fromstring(result)
    assert root.tag == "mxfile"


def test_drawio_erd_contains_tables():
    result = render_erd_drawio(_sample_db())
    assert "users" in result
    assert "departments" in result


def test_drawio_sequence_valid_xml():
    api = ApiSchema(endpoints=[
        Endpoint(method="POST", path="/api/users", controller="UserController",
                 service="UserService", calls=["UserRepository.save"]),
    ])
    result = render_sequence_drawio(
        api, DependencySchema(),
        entries=["UserController", "UserService", "UserRepository.save"],
        label="사용자 생성",
    )
    root = ET.fromstring(result)
    assert root.tag == "mxfile"
    assert "UserController" in result


def test_drawio_architecture_valid_xml():
    scan = ScanResult(project="test")
    scan.database = _sample_db()
    scan.api = ApiSchema(endpoints=[
        Endpoint(method="GET", path="/api/users", controller="UserController",
                 service="UserService", calls=["UserRepository.findAll"]),
    ])
    result = render_architecture_drawio(scan)
    root = ET.fromstring(result)
    assert root.tag == "mxfile"


def test_drawio_component_valid_xml():
    deps = DependencySchema(modules=[
        Module(name="UserService", type="service", file="a.java",
               dependsOn=["UserRepository"], layer="service"),
    ])
    result = render_component_drawio(deps)
    root = ET.fromstring(result)
    assert root.tag == "mxfile"
    assert "UserService" in result
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/renderer/test_drawio.py -v`
Expected: FAIL

- [ ] **Step 3: Implement draw.io renderer**

Generate draw.io XML format (mxfile/mxGraphModel) with cells for tables/modules as nodes and edges for relationships.

*(Implementation in `src/codemap/renderer/drawio.py`)*

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/renderer/test_drawio.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/codemap/renderer/drawio.py tests/renderer/test_drawio.py
git commit -m "feat: implement draw.io renderer for ERD and component diagrams"
```

---

## Task 10: `render` CLI Command

**Files:**
- Modify: `src/codemap/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write failing test**

```python
# Add to tests/test_cli.py
def test_cli_render_erd_mermaid(tmp_path):
    # First create scan JSON
    scan_file = tmp_path / "scan.json"
    runner = CliRunner()
    runner.invoke(main, ["scan", str(FIXTURE_DIR), "-o", str(scan_file), "--target", "db"])

    output_file = tmp_path / "erd.mmd"
    result = runner.invoke(main, ["render", "erd", "--from", str(scan_file), "--format", "mermaid", "-o", str(output_file)])
    assert result.exit_code == 0
    content = output_file.read_text()
    assert "erDiagram" in content


def test_cli_render_erd_drawio(tmp_path):
    scan_file = tmp_path / "scan.json"
    runner = CliRunner()
    runner.invoke(main, ["scan", str(FIXTURE_DIR), "-o", str(scan_file), "--target", "db"])

    output_file = tmp_path / "erd.drawio"
    result = runner.invoke(main, ["render", "erd", "--from", str(scan_file), "--format", "drawio", "-o", str(output_file)])
    assert result.exit_code == 0
    content = output_file.read_text()
    assert "mxfile" in content
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_cli.py::test_cli_render_erd_mermaid -v`
Expected: FAIL

- [ ] **Step 3: Add `render` command to CLI**

Add `render` Click command that reads scan JSON, dispatches to mermaid or drawio renderer based on `--format`, supports `--entries` and `--label` for sequence diagrams.

*(Add to `src/codemap/cli.py`)*

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_cli.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/codemap/cli.py tests/test_cli.py
git commit -m "feat: add render command to CLI for diagram generation"
```

---

## Task 11: Doc Generators (table-spec, api-spec, overview)

**Files:**
- Create: `src/codemap/doc/__init__.py`
- Create: `src/codemap/doc/table_spec.py`
- Create: `src/codemap/doc/api_spec.py`
- Create: `src/codemap/doc/overview.py`
- Create: `tests/doc/test_table_spec.py`
- Create: `tests/doc/test_api_spec.py`
- Create: `tests/doc/test_overview.py`

- [ ] **Step 1: Write failing test for table-spec**

```python
# tests/doc/test_table_spec.py
from codemap.models import DatabaseSchema, Table, Column, ForeignKey, Index
from codemap.doc.table_spec import generate_table_spec


def _sample_db():
    return DatabaseSchema(tables=[
        Table(name="users", columns=[
            Column(name="id", type="BIGINT", pk=True, nullable=False),
            Column(name="email", type="VARCHAR(255)", nullable=False),
            Column(name="dept_id", type="BIGINT"),
        ], foreignKeys=[ForeignKey(column="dept_id", references="departments.id")],
        indexes=[Index(name="idx_users_email", columns=["email"], unique=True)]),
    ])


def test_table_spec_header():
    md = generate_table_spec(_sample_db())
    assert "# 테이블 정의서" in md


def test_table_spec_table_section():
    md = generate_table_spec(_sample_db())
    assert "## users" in md
    assert "| 컬럼명 |" in md
    assert "| id |" in md or "|id|" in md or "| id " in md


def test_table_spec_pk_marker():
    md = generate_table_spec(_sample_db())
    assert "O" in md  # PK marker


def test_table_spec_fk():
    md = generate_table_spec(_sample_db())
    assert "departments.id" in md


def test_table_spec_index():
    md = generate_table_spec(_sample_db())
    assert "idx_users_email" in md
    assert "UNIQUE" in md


def test_table_spec_empty():
    md = generate_table_spec(DatabaseSchema())
    assert "# 테이블 정의서" in md
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/doc/test_table_spec.py -v`
Expected: FAIL

- [ ] **Step 3: Implement table_spec, api_spec, overview**

```python
# src/codemap/doc/__init__.py
```

Table spec: Markdown table per DB table with columns (컬럼명, 타입, PK, FK, Nullable, 설명) + index section.
API spec: Markdown table of endpoints (메서드, 경로, 컨트롤러, 서비스, 호출).
Overview: Project summary with tech stack, module structure, external dependencies.

*(Implementation in `src/codemap/doc/table_spec.py`, `api_spec.py`, `overview.py`)*

- [ ] **Step 4: Write api_spec and overview tests**

```python
# tests/doc/test_api_spec.py
from codemap.models import ApiSchema, Endpoint
from codemap.doc.api_spec import generate_api_spec


def test_api_spec_header():
    md = generate_api_spec(ApiSchema(endpoints=[
        Endpoint(method="GET", path="/api/users", controller="UserController",
                 service="UserService", calls=["UserRepository.findAll"]),
    ]))
    assert "# API 명세서" in md
    assert "GET" in md
    assert "/api/users" in md
    assert "UserController" in md


def test_api_spec_empty():
    md = generate_api_spec(ApiSchema())
    assert "# API 명세서" in md
```

```python
# tests/doc/test_overview.py
from codemap.models import ScanResult, DatabaseSchema, Table, Column, ApiSchema, Endpoint, DependencySchema, ExternalCall
from codemap.doc.overview import generate_overview


def test_overview_contains_sections():
    scan = ScanResult(project="my-project")
    scan.database = DatabaseSchema(tables=[
        Table(name="users", columns=[Column(name="id", type="BIGINT", pk=True)]),
    ])
    scan.api = ApiSchema(endpoints=[
        Endpoint(method="GET", path="/api/users", controller="UserController",
                 service="UserService", calls=[]),
    ])
    scan.dependencies = DependencySchema(externalCalls=[
        ExternalCall(source="GdalService.convert", type="process",
                     command="gdal_translate", file="GdalService.java", line=42),
    ])
    md = generate_overview(scan)
    assert "# 프로젝트 개요" in md
    assert "my-project" in md


def test_overview_empty():
    md = generate_overview(ScanResult(project="empty"))
    assert "# 프로젝트 개요" in md
```

- [ ] **Step 5: Run all doc tests**

Run: `python3 -m pytest tests/doc/ -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/codemap/doc/ tests/doc/
git commit -m "feat: implement doc generators for table-spec, api-spec, overview"
```

---

## Task 12: `doc` CLI Command

**Files:**
- Modify: `src/codemap/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write failing test**

```python
# Add to tests/test_cli.py
def test_cli_doc_table_spec(tmp_path):
    scan_file = tmp_path / "scan.json"
    runner = CliRunner()
    runner.invoke(main, ["scan", str(FIXTURE_DIR), "-o", str(scan_file), "--target", "db"])

    output_file = tmp_path / "table-spec.md"
    result = runner.invoke(main, ["doc", "table-spec", "--from", str(scan_file), "-o", str(output_file)])
    assert result.exit_code == 0
    content = output_file.read_text()
    assert "# 테이블 정의서" in content
```

- [ ] **Step 2: Run test, verify fail, implement, verify pass**

- [ ] **Step 3: Commit**

```bash
git add src/codemap/cli.py tests/test_cli.py
git commit -m "feat: add doc command to CLI for markdown document generation"
```

---

## Task 13: Excel Export

**Files:**
- Create: `src/codemap/export/__init__.py`
- Create: `src/codemap/export/xlsx.py`
- Create: `tests/export/test_xlsx.py`

- [ ] **Step 1: Write failing test**

```python
# tests/export/test_xlsx.py
from pathlib import Path

import openpyxl

from codemap.models import (
    ScanResult, DatabaseSchema, Table, Column, ForeignKey, Index,
    ApiSchema, Endpoint,
)
from codemap.export.xlsx import export_table_spec_xlsx, export_api_spec_xlsx


def _sample_scan():
    return ScanResult(
        project="test",
        database=DatabaseSchema(tables=[
            Table(name="users", columns=[
                Column(name="id", type="BIGINT", pk=True, nullable=False),
                Column(name="email", type="VARCHAR(255)", nullable=False),
            ], foreignKeys=[ForeignKey(column="dept_id", references="departments.id")],
            indexes=[Index(name="idx_email", columns=["email"], unique=True)]),
            Table(name="departments", columns=[
                Column(name="id", type="BIGINT", pk=True, nullable=False),
                Column(name="name", type="VARCHAR(255)", nullable=False),
            ]),
        ]),
        api=ApiSchema(endpoints=[
            Endpoint(method="GET", path="/api/users", controller="UserController",
                     service="UserService", calls=["UserRepository.findAll"]),
        ]),
    )


def test_export_table_spec_xlsx(tmp_path):
    output = tmp_path / "table-spec.xlsx"
    export_table_spec_xlsx(_sample_scan(), output)
    assert output.exists()

    wb = openpyxl.load_workbook(output)
    assert "목차" in wb.sheetnames
    assert "users" in wb.sheetnames
    assert "departments" in wb.sheetnames


def test_export_table_spec_xlsx_index_sheet(tmp_path):
    output = tmp_path / "table-spec.xlsx"
    export_table_spec_xlsx(_sample_scan(), output)
    wb = openpyxl.load_workbook(output)
    ws = wb["목차"]
    # Header row + 2 data rows
    assert ws.max_row >= 3


def test_export_table_spec_xlsx_table_sheet(tmp_path):
    output = tmp_path / "table-spec.xlsx"
    export_table_spec_xlsx(_sample_scan(), output)
    wb = openpyxl.load_workbook(output)
    ws = wb["users"]
    # Should have header + 2 columns
    assert ws.max_row >= 3
    assert ws.cell(1, 2).value == "컬럼명"  # Header check


def test_export_api_spec_xlsx(tmp_path):
    output = tmp_path / "api-spec.xlsx"
    export_api_spec_xlsx(_sample_scan(), output)
    assert output.exists()
    wb = openpyxl.load_workbook(output)
    assert "엔드포인트 목록" in wb.sheetnames
```

- [ ] **Step 2: Run test, verify fail, implement, verify pass**

- [ ] **Step 3: Commit**

```bash
git add src/codemap/export/ tests/export/
git commit -m "feat: implement Excel export for table-spec and api-spec"
```

---

## Task 14: PDF Export (Optional Dependency)

**Files:**
- Create: `src/codemap/export/pdf.py`
- Create: `tests/export/test_pdf.py`
- Create: `.codemap/templates/minimal.css`

- [ ] **Step 1: Write failing test**

```python
# tests/export/test_pdf.py
import pytest
from pathlib import Path

from codemap.export.pdf import export_pdf


def test_export_pdf_from_markdown(tmp_path):
    pytest.importorskip("weasyprint")
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "test.md").write_text("# Test\n\nHello world\n")

    output = tmp_path / "report.pdf"
    export_pdf(docs_dir, output)
    assert output.exists()
    assert output.stat().st_size > 0


def test_export_pdf_missing_weasyprint(monkeypatch):
    import codemap.export.pdf as pdf_mod
    monkeypatch.setattr(pdf_mod, "HAS_WEASYPRINT", False)
    with pytest.raises(ImportError, match="pip install codemap\\[pdf\\]"):
        export_pdf(Path("/tmp"), Path("/tmp/out.pdf"))
```

- [ ] **Step 2: Run test, verify fail, implement, verify pass**

- [ ] **Step 3: Commit**

```bash
git add src/codemap/export/pdf.py tests/export/test_pdf.py .codemap/
git commit -m "feat: implement PDF export with optional weasyprint dependency"
```

---

## Task 15: Word Export (Optional Dependency)

**Files:**
- Create: `src/codemap/export/docx_export.py`
- Create: `tests/export/test_docx_export.py`

- [ ] **Step 1: Write failing test**

```python
# tests/export/test_docx_export.py
import pytest
from pathlib import Path

from codemap.export.docx_export import export_docx


def test_export_docx_from_markdown(tmp_path):
    pytest.importorskip("docx")
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "test.md").write_text("# Test\n\nHello world\n\n## Section\n\nContent here.\n")

    output = tmp_path / "report.docx"
    export_docx(docs_dir, output)
    assert output.exists()
    assert output.stat().st_size > 0


def test_export_docx_missing_dependency(monkeypatch):
    import codemap.export.docx_export as docx_mod
    monkeypatch.setattr(docx_mod, "HAS_DOCX", False)
    with pytest.raises(ImportError, match="pip install codemap\\[docx\\]"):
        export_docx(Path("/tmp"), Path("/tmp/out.docx"))
```

- [ ] **Step 2: Run test, verify fail, implement, verify pass**

- [ ] **Step 3: Commit**

```bash
git add src/codemap/export/docx_export.py tests/export/test_docx_export.py
git commit -m "feat: implement Word export with optional python-docx dependency"
```

---

## Task 16: `export` CLI Command

**Files:**
- Modify: `src/codemap/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write failing test**

```python
# Add to tests/test_cli.py
def test_cli_export_xlsx(tmp_path):
    scan_file = tmp_path / "scan.json"
    runner = CliRunner()
    runner.invoke(main, ["scan", str(FIXTURE_DIR), "-o", str(scan_file), "--target", "db"])

    output_file = tmp_path / "table-spec.xlsx"
    result = runner.invoke(main, [
        "export", "xlsx", "--from", str(scan_file),
        "--type", "table-spec", "-o", str(output_file)
    ])
    assert result.exit_code == 0
    assert output_file.exists()


def test_cli_export_pdf_with_template(tmp_path):
    pytest.importorskip("weasyprint")
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "test.md").write_text("# Test\n\nHello\n")

    output_file = tmp_path / "report.pdf"
    result = runner.invoke(main, [
        "export", "pdf", "--from", str(docs_dir),
        "--template", "minimal", "-o", str(output_file)
    ])
    assert result.exit_code == 0


def test_cli_export_pdf_from_scan_json(tmp_path):
    """PDF export from scan JSON auto-chains: scan JSON → doc → PDF"""
    pytest.importorskip("weasyprint")
    scan_file = tmp_path / "scan.json"
    runner = CliRunner()
    runner.invoke(main, ["scan", str(FIXTURE_DIR), "-o", str(scan_file), "--target", "db"])

    output_file = tmp_path / "report.pdf"
    result = runner.invoke(main, [
        "export", "pdf", "--from", str(scan_file), "-o", str(output_file)
    ])
    assert result.exit_code == 0
    assert output_file.exists()
```

- [ ] **Step 2: Run test, verify fail**

- [ ] **Step 3: Implement export CLI command**

The `export` command must:
- Accept `--template` option (corporate/minimal)
- Accept `--type` option (required for xlsx)
- Detect if `--from` is a JSON file or directory
- If JSON + pdf/docx format: auto-chain through doc generation first, then export
- Wire template path resolution: project `.codemap/templates/` → `~/.codemap/templates/`

- [ ] **Step 4: Run test, verify pass**

- [ ] **Step 5: Commit**

```bash
git add src/codemap/cli.py tests/test_cli.py
git commit -m "feat: add export command with template support and JSON auto-chaining"
```

---

## Task 17: `generate` Pipeline Command

**Files:**
- Modify: `src/codemap/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write failing test**

```python
# Add to tests/test_cli.py
def test_cli_generate(tmp_path):
    output_dir = tmp_path / "output"
    runner = CliRunner()
    result = runner.invoke(main, [
        "generate", str(FIXTURE_DIR), "-o", str(output_dir),
        "--target", "db", "--format", "mermaid"
    ])
    assert result.exit_code == 0
    # Should have created scan JSON, diagrams, and docs
    assert (output_dir / "diagrams").exists() or any(output_dir.rglob("*.mmd"))
    assert any(output_dir.rglob("*.md"))


def test_cli_generate_with_export(tmp_path):
    output_dir = tmp_path / "output"
    runner = CliRunner()
    result = runner.invoke(main, [
        "generate", str(FIXTURE_DIR), "-o", str(output_dir),
        "--target", "db", "--format", "mermaid", "--export", "xlsx"
    ])
    assert result.exit_code == 0
    assert any(output_dir.rglob("*.xlsx"))
```

- [ ] **Step 2: Run test, verify fail, implement, verify pass**

- [ ] **Step 3: Commit**

```bash
git add src/codemap/cli.py tests/test_cli.py
git commit -m "feat: add generate command for full pipeline execution"
```

---

## Task 18: Integration Test

**Files:**
- Create: `tests/test_integration.py`

- [ ] **Step 1: Write integration test**

```python
# tests/test_integration.py
"""Full pipeline integration test: scan → render → doc → export"""
import json
from pathlib import Path

from click.testing import CliRunner
from codemap.cli import main

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def test_full_pipeline(tmp_path):
    runner = CliRunner()

    # 1. Scan
    scan_file = tmp_path / "scan.json"
    result = runner.invoke(main, ["scan", str(FIXTURE_DIR), "-o", str(scan_file), "--target", "db"])
    assert result.exit_code == 0

    # 2. Render ERD
    erd_file = tmp_path / "erd.mmd"
    result = runner.invoke(main, ["render", "erd", "--from", str(scan_file), "--format", "mermaid", "-o", str(erd_file)])
    assert result.exit_code == 0
    assert "erDiagram" in erd_file.read_text()

    # 3. Doc table-spec
    doc_file = tmp_path / "table-spec.md"
    result = runner.invoke(main, ["doc", "table-spec", "--from", str(scan_file), "-o", str(doc_file)])
    assert result.exit_code == 0
    assert "# 테이블 정의서" in doc_file.read_text()

    # 4. Export xlsx
    xlsx_file = tmp_path / "table-spec.xlsx"
    result = runner.invoke(main, ["export", "xlsx", "--from", str(scan_file), "--type", "table-spec", "-o", str(xlsx_file)])
    assert result.exit_code == 0
    assert xlsx_file.exists()


def test_scan_multi_target(tmp_path):
    """Verify comma-separated --target works (spec line 81)"""
    scan_file = tmp_path / "scan.json"
    runner = CliRunner()
    result = runner.invoke(main, ["scan", str(FIXTURE_DIR), "-o", str(scan_file), "--target", "db,api"])
    assert result.exit_code == 0
    data = json.loads(scan_file.read_text())
    assert len(data["database"]["tables"]) > 0


def test_render_all(tmp_path):
    """Verify render all generates all diagram types"""
    scan_file = tmp_path / "scan.json"
    runner = CliRunner()
    runner.invoke(main, ["scan", str(FIXTURE_DIR), "-o", str(scan_file), "--target", "db"])

    output_dir = tmp_path / "diagrams"
    result = runner.invoke(main, [
        "render", "all", "--from", str(scan_file), "--format", "mermaid", "-o", str(output_dir)
    ])
    assert result.exit_code == 0


def test_doc_all(tmp_path):
    """Verify doc all generates all document types"""
    scan_file = tmp_path / "scan.json"
    runner = CliRunner()
    runner.invoke(main, ["scan", str(FIXTURE_DIR), "-o", str(scan_file), "--target", "db"])

    output_dir = tmp_path / "docs"
    result = runner.invoke(main, [
        "doc", "all", "--from", str(scan_file), "-o", str(output_dir)
    ])
    assert result.exit_code == 0
```

- [ ] **Step 2: Run integration test**

Run: `python3 -m pytest tests/test_integration.py -v`
Expected: All PASS

- [ ] **Step 3: Run full test suite**

Run: `python3 -m pytest -v`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_integration.py
git commit -m "test: add full pipeline integration test with multi-target and all commands"
```

---

## Task 19: Claude Code Skill File

**Files:**
- Create: `skill/codemap.md` (in project, to be copied to `~/.claude/skills/` on install)

- [ ] **Step 1: Create the skill file**

```markdown
---
name: codemap
description: 코드베이스를 분석하여 테이블 정의서, ERD, 시퀀스 다이어그램,
             아키텍처 다이어그램 등 기술 문서를 자동 생성
---

## 사용 가능한 명령어

- `codemap scan <path> [--target db|api|deps|frontend|all] [-o output.json]`
- `codemap render <erd|sequence|architecture|component|all> --from <json> --format <mermaid|drawio>`
  - sequence 전용: `--entries "Class.method,..." --label "유스케이스명"`
- `codemap doc <table-spec|api-spec|overview|all> --from <json> [-o output]`
- `codemap export <pdf|docx|xlsx> --from <json|docs/> [-o output]`
  - xlsx는 반드시 scan JSON을 입력으로 사용: `--from scan.json --type table-spec|api-spec`
- `codemap generate <path> -o <output/> [--format all] [--export all]`

## 에이전트 워크플로우

1. `codemap scan` 실행하여 프로젝트 분석 데이터 획득
2. JSON 결과를 읽고 프로젝트 구조 파악
3. 사용자 요청에 따라 적절한 다이어그램/문서 유형 판단
4. 시퀀스 다이어그램: JSON에서 관련 API 엔드포인트와 호출 체인을 분석하여
   유스케이스 단위로 묶고 `--entries` 옵션으로 전달
5. 생성된 산출물을 사용자에게 안내

## 주의사항

- scan 결과 JSON은 `.codemap/scan.json`에 캐싱하여 재사용 가능
- xlsx export는 마크다운이 아닌 scan JSON에서 직접 생성
- weasyprint 미설치 시 PDF export 불가 — 사용자에게 설치 안내
```

- [ ] **Step 2: Commit**

```bash
git add skill/
git commit -m "feat: add Claude Code skill file for codemap"
```

---

## Task 20: Final Cleanup

**Files:**
- Verify all `__init__.py` files exist
- Verify `pip install -e .` works cleanly
- Verify `codemap --help` shows all commands

- [ ] **Step 1: Verify install and help**

```bash
pip install -e ".[all]"
codemap --help
codemap scan --help
codemap render --help
codemap doc --help
codemap export --help
codemap generate --help
```

- [ ] **Step 2: Run full test suite one final time**

Run: `python3 -m pytest -v --tb=short`
Expected: All PASS

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "chore: final cleanup and verify all commands"
```
