# LLM Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add LLM enrichment to Codemap's scan and doc pipeline using a self-hosted Ollama server, enabling automatic generation of table/column descriptions, API summaries, external call purposes, table relationships, business logic summaries, and project overviews.

**Architecture:** A new `src/codemap/ai/` module provides an HTTP client (`AiClient`) that talks to Ollama's OpenAI-compatible API. `enrich_scan.py` enriches `ScanResult` after scanning, and `enrich_doc.py` provides helper functions called by existing `generate_*` doc functions. LLM enrichment is on by default; `--no-ai` disables it. Connection failures trigger graceful degradation.

**Tech Stack:** Python 3.12+, urllib.request (no new dependencies), Ollama OpenAI-compatible API

**Spec:** `docs/superpowers/specs/2026-03-25-llm-integration-design.md`

---

## File Structure

### New Files
| File | Responsibility |
|------|---------------|
| `src/codemap/ai/__init__.py` | Package init, re-exports `AiClient` and `AiConfig` |
| `src/codemap/ai/client.py` | `AiClient` class: HTTP client for Ollama `/v1/chat/completions` |
| `src/codemap/ai/enrich_scan.py` | `enrich_scan()`: enriches ScanResult with table/column descriptions, endpoint summaries, external call purposes |
| `src/codemap/ai/enrich_doc.py` | Helper functions: `generate_table_relationships()`, `generate_business_logic()`, `generate_overview_narrative()` |
| `tests/ai/__init__.py` | Test package init |
| `tests/ai/test_client.py` | Tests for `AiClient` |
| `tests/ai/test_enrich_scan.py` | Tests for scan enrichment |
| `tests/ai/test_enrich_doc.py` | Tests for doc enrichment helpers |

### Modified Files
| File | Change |
|------|--------|
| `src/codemap/models.py` | Add `description: str = ""` to `Endpoint` and `ExternalCall` |
| `src/codemap/config.py` | Add `AiConfig` class and `ai` field to `CodemapConfig` |
| `src/codemap/cli.py` | Add `--no-ai` flag, wire AI client into `scan`, `doc`, `generate`, `export` commands |
| `src/codemap/doc/table_spec.py` | Accept `ai_client` param, call `generate_table_relationships()` |
| `src/codemap/doc/api_spec.py` | Accept `ai_client` param, call `generate_business_logic()` |
| `src/codemap/doc/overview.py` | Accept `ai_client` param, call `generate_overview_narrative()` |

---

### Task 1: Model Changes — Add `description` Fields

**Files:**
- Modify: `src/codemap/models.py:53-62` (Endpoint)
- Modify: `src/codemap/models.py:78-85` (ExternalCall)
- Test: `tests/test_models.py`

- [ ] **Step 1: Write tests for new `description` field on Endpoint**

In `tests/test_models.py`, add:

```python
def test_endpoint_description_default():
    ep = Endpoint(
        method="GET", path="/api/users",
        controller="UserController", service="UserService",
    )
    assert ep.description == ""


def test_endpoint_description_set():
    ep = Endpoint(
        method="GET", path="/api/users",
        controller="UserController", service="UserService",
        description="사용자 목록을 조회하는 API",
    )
    assert ep.description == "사용자 목록을 조회하는 API"
```

- [ ] **Step 2: Write tests for new `description` field on ExternalCall**

In `tests/test_models.py`, add:

```python
def test_external_call_description_default():
    ec = ExternalCall(
        source="GdalService", type="gdal",
        command="gdal_translate", file="GdalService.java", line=10,
    )
    assert ec.description == ""


def test_external_call_description_set():
    ec = ExternalCall(
        source="GdalService", type="gdal",
        command="gdal_translate", file="GdalService.java", line=10,
        description="래스터 이미지 형식 변환",
    )
    assert ec.description == "래스터 이미지 형식 변환"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_models.py::test_endpoint_description_default tests/test_models.py::test_endpoint_description_set tests/test_models.py::test_external_call_description_default tests/test_models.py::test_external_call_description_set -v`
Expected: FAIL

- [ ] **Step 4: Add `description` field to `Endpoint` and `ExternalCall`**

In `src/codemap/models.py`, add `description: str = ""` to `Endpoint` (after `responseFields`):

```python
class Endpoint(BaseModel):
    method: str
    path: str
    controller: str
    service: str
    calls: list[str] = Field(default_factory=list)
    params: list[Param] = Field(default_factory=list)
    returnType: str = ""
    requestFields: list[JavaField] = Field(default_factory=list)
    responseFields: list[JavaField] = Field(default_factory=list)
    description: str = ""
```

In `ExternalCall`, add `description: str = ""` (after `line`):

```python
class ExternalCall(BaseModel):
    source: str = Field(alias="from", serialization_alias="from")
    type: str
    command: str
    file: str
    line: int
    description: str = ""

    model_config = {"populate_by_name": True}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_models.py -v`
Expected: ALL PASS

- [ ] **Step 6: Run full test suite to verify no regressions**

Run: `pytest tests/ -v`
Expected: ALL PASS (new fields have defaults, so existing tests are unaffected)

- [ ] **Step 7: Commit**

```bash
git add src/codemap/models.py tests/test_models.py
git commit -m "feat: add description field to Endpoint and ExternalCall models"
```

---

### Task 2: Config Changes — Add `AiConfig`

**Files:**
- Modify: `src/codemap/config.py:54-65`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write tests for AiConfig defaults**

In `tests/test_config.py`, add:

```python
def test_default_config_has_ai():
    cfg = DEFAULT_CONFIG
    assert cfg.ai.enabled is True
    assert cfg.ai.base_url == "http://183.101.208.30:63001"
    assert cfg.ai.model == "qwen3:30b-a3b-instruct-2507-fp16"
    assert cfg.ai.language == "ko"


def test_load_config_with_ai_override(tmp_path):
    config_dir = tmp_path / ".codemap"
    config_dir.mkdir()
    config_file = config_dir / "config.yaml"
    config_file.write_text(
        "ai:\n  enabled: false\n  model: qwen3.5:9b\n"
    )
    cfg = load_config(tmp_path)
    assert cfg.ai.enabled is False
    assert cfg.ai.model == "qwen3.5:9b"
    # Non-overridden ai fields keep defaults
    assert cfg.ai.language == "ko"


def test_load_config_without_ai_section(tmp_path):
    config_dir = tmp_path / ".codemap"
    config_dir.mkdir()
    config_file = config_dir / "config.yaml"
    config_file.write_text("project:\n  name: my-proj\n")
    cfg = load_config(tmp_path)
    assert cfg.ai.enabled is True
    assert cfg.ai.language == "ko"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_config.py::test_default_config_has_ai tests/test_config.py::test_load_config_with_ai_override tests/test_config.py::test_load_config_without_ai_section -v`
Expected: FAIL (no `ai` attribute on CodemapConfig)

- [ ] **Step 3: Add `AiConfig` to config.py**

In `src/codemap/config.py`, add the `AiConfig` class before `CodemapConfig`, and add the `ai` field:

```python
class AiConfig(BaseModel):
    enabled: bool = True
    base_url: str = "http://183.101.208.30:63001"
    model: str = "qwen3:30b-a3b-instruct-2507-fp16"
    language: str = "ko"


class CodemapConfig(BaseModel):
    project: ProjectConfig = Field(default_factory=ProjectConfig)
    scan: ScanConfig = Field(default_factory=ScanConfig)
    export: ExportConfig = Field(default_factory=ExportConfig)
    ai: AiConfig = Field(default_factory=AiConfig)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_config.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/codemap/config.py tests/test_config.py
git commit -m "feat: add AiConfig to CodemapConfig with Ollama defaults"
```

---

### Task 3: AI Client — `AiClient` Class

**Files:**
- Create: `src/codemap/ai/__init__.py`
- Create: `src/codemap/ai/client.py`
- Create: `tests/ai/__init__.py`
- Create: `tests/ai/test_client.py`

- [ ] **Step 1: Create package init files**

Create `src/codemap/ai/__init__.py`:

```python
from codemap.ai.client import AiClient

__all__ = ["AiClient"]
```

Create `tests/ai/__init__.py` (empty file).

- [ ] **Step 2: Write tests for AiClient**

Create `tests/ai/test_client.py`:

```python
import json
from unittest.mock import patch, MagicMock
from codemap.ai.client import AiClient


def test_client_init():
    client = AiClient("http://localhost:11434", "qwen3:30b", "ko")
    assert client.base_url == "http://localhost:11434"
    assert client.model == "qwen3:30b"
    assert client.language == "ko"
    assert client.available is True


def test_client_strips_trailing_slash():
    client = AiClient("http://localhost:11434/", "qwen3:30b")
    assert client.base_url == "http://localhost:11434"


def test_chat_returns_content():
    client = AiClient("http://localhost:11434", "qwen3:30b")
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps({
        "choices": [{"message": {"content": "Hello world"}}]
    }).encode()
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen", return_value=mock_response):
        result = client.chat("system msg", "user msg")
    assert result == "Hello world"
    assert client.available is True


def test_chat_connection_refused_disables():
    client = AiClient("http://localhost:11434", "qwen3:30b")
    with patch("urllib.request.urlopen", side_effect=ConnectionRefusedError):
        result = client.chat("system", "user")
    assert result == ""
    assert client.available is False


def test_chat_disabled_returns_empty_immediately():
    client = AiClient("http://localhost:11434", "qwen3:30b")
    client._disabled = True
    # Should not make any HTTP call
    result = client.chat("system", "user")
    assert result == ""


def test_chat_timeout_retries_once():
    client = AiClient("http://localhost:11434", "qwen3:30b")
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps({
        "choices": [{"message": {"content": "OK"}}]
    }).encode()
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)

    from urllib.error import URLError
    import socket
    timeout_err = URLError(socket.timeout("timed out"))

    with patch("urllib.request.urlopen", side_effect=[timeout_err, mock_response]):
        result = client.chat("system", "user")
    assert result == "OK"
    assert client.available is True


def test_chat_timeout_twice_disables():
    client = AiClient("http://localhost:11434", "qwen3:30b")
    from urllib.error import URLError
    import socket
    timeout_err = URLError(socket.timeout("timed out"))

    with patch("urllib.request.urlopen", side_effect=[timeout_err, timeout_err]):
        result = client.chat("system", "user")
    assert result == ""
    assert client.available is False


def test_chat_http_5xx_retries_once():
    client = AiClient("http://localhost:11434", "qwen3:30b")
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps({
        "choices": [{"message": {"content": "OK"}}]
    }).encode()
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)

    from urllib.error import HTTPError
    err_500 = HTTPError("http://localhost", 500, "Internal Server Error", {}, None)

    with patch("urllib.request.urlopen", side_effect=[err_500, mock_response]):
        result = client.chat("system", "user")
    assert result == "OK"
    assert client.available is True


def test_chat_http_5xx_twice_disables():
    client = AiClient("http://localhost:11434", "qwen3:30b")
    from urllib.error import HTTPError
    err_500 = HTTPError("http://localhost", 500, "Internal Server Error", {}, None)

    with patch("urllib.request.urlopen", side_effect=[err_500, err_500]):
        result = client.chat("system", "user")
    assert result == ""
    assert client.available is False


def test_chat_json_parses_response():
    client = AiClient("http://localhost:11434", "qwen3:30b")
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps({
        "choices": [{"message": {"content": '{"key": "value"}'}}]
    }).encode()
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen", return_value=mock_response):
        result = client.chat_json("system", "user")
    assert result == {"key": "value"}


def test_chat_json_strips_code_fence():
    client = AiClient("http://localhost:11434", "qwen3:30b")
    mock_response = MagicMock()
    fenced = '```json\n{"key": "value"}\n```'
    mock_response.read.return_value = json.dumps({
        "choices": [{"message": {"content": fenced}}]
    }).encode()
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen", return_value=mock_response):
        result = client.chat_json("system", "user")
    assert result == {"key": "value"}


def test_chat_json_returns_none_on_invalid_json():
    client = AiClient("http://localhost:11434", "qwen3:30b")
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps({
        "choices": [{"message": {"content": "not json at all"}}]
    }).encode()
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen", return_value=mock_response):
        result = client.chat_json("system", "user")
    assert result is None
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/ai/test_client.py -v`
Expected: FAIL (module not found)

- [ ] **Step 4: Implement `AiClient`**

Create `src/codemap/ai/client.py`:

```python
from __future__ import annotations

import json
import logging
import re
import socket
import urllib.request
import urllib.error

logger = logging.getLogger(__name__)

_TIMEOUT = 60
_RETRYABLE = (socket.timeout, TimeoutError)


class AiClient:
    def __init__(self, base_url: str, model: str, language: str = "ko"):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.language = language
        self._disabled = False

    @property
    def available(self) -> bool:
        return not self._disabled

    def chat(self, system: str, user: str, temperature: float = 0.3) -> str:
        if self._disabled:
            return ""

        body = json.dumps({
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "stream": False,
        }).encode()

        url = f"{self.base_url}/v1/chat/completions"
        req = urllib.request.Request(
            url, data=body,
            headers={"Content-Type": "application/json"},
        )

        for attempt in range(2):
            try:
                with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
                    data = json.loads(resp.read())
                return data["choices"][0]["message"]["content"]
            except ConnectionRefusedError:
                logger.warning("AI server connection refused — disabling AI enrichment")
                self._disabled = True
                return ""
            except urllib.error.URLError as e:
                if isinstance(e.reason, _RETRYABLE) and attempt == 0:
                    logger.info("AI request timed out, retrying...")
                    continue
                logger.warning("AI server unreachable — disabling AI enrichment: %s", e)
                self._disabled = True
                return ""
            except (urllib.error.HTTPError, OSError) as e:
                if attempt == 0:
                    logger.info("AI request failed (%s), retrying...", e)
                    continue
                logger.warning("AI server error — disabling AI enrichment: %s", e)
                self._disabled = True
                return ""
            except (KeyError, json.JSONDecodeError) as e:
                logger.warning("AI response parse error: %s", e)
                return ""

        return ""

    def chat_json(self, system: str, user: str, temperature: float = 0.3) -> dict | None:
        text = self.chat(system, user, temperature)
        if not text:
            return None

        # Strip markdown code fences
        stripped = re.sub(r"^```(?:json)?\s*\n?", "", text.strip())
        stripped = re.sub(r"\n?```\s*$", "", stripped)

        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            logger.warning("AI returned invalid JSON: %s", text[:200])
            return None
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/ai/test_client.py -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add src/codemap/ai/__init__.py src/codemap/ai/client.py tests/ai/__init__.py tests/ai/test_client.py
git commit -m "feat: add AiClient with Ollama OpenAI-compatible API support"
```

---

### Task 4: Scan Enrichment — `enrich_scan.py`

**Files:**
- Create: `src/codemap/ai/enrich_scan.py`
- Create: `tests/ai/test_enrich_scan.py`

- [ ] **Step 1: Write tests for table/column enrichment (Feature 1)**

Create `tests/ai/test_enrich_scan.py`:

```python
import json
from unittest.mock import patch, MagicMock, call
from codemap.models import (
    ScanResult, DatabaseSchema, Table, Column, ForeignKey,
    ApiSchema, Endpoint, Param, JavaField,
    DependencySchema, ExternalCall, Module,
)
from codemap.ai.client import AiClient
from codemap.ai.enrich_scan import enrich_scan


def _make_client():
    return AiClient("http://localhost:11434", "qwen3:30b", "ko")


def test_enrich_table_comments():
    result = ScanResult(
        project="test",
        database=DatabaseSchema(tables=[
            Table(name="users", columns=[
                Column(name="id", type="BIGINT", pk=True, nullable=False),
                Column(name="email", type="VARCHAR(255)"),
            ]),
        ]),
    )
    client = _make_client()
    ai_response = {
        "table_comment": "사용자 정보를 관리하는 테이블",
        "columns": {
            "id": "사용자 고유 식별자",
            "email": "사용자 이메일 주소",
        },
    }
    with patch.object(client, "chat_json", return_value=ai_response):
        enrich_scan(result, client)

    assert result.database.tables[0].comment == "사용자 정보를 관리하는 테이블"
    assert result.database.tables[0].columns[0].comment == "사용자 고유 식별자"
    assert result.database.tables[0].columns[1].comment == "사용자 이메일 주소"


def test_enrich_skips_existing_comments():
    result = ScanResult(
        project="test",
        database=DatabaseSchema(tables=[
            Table(name="users", comment="기존 설명", columns=[
                Column(name="id", type="BIGINT", comment="기존 컬럼 설명"),
            ]),
        ]),
    )
    client = _make_client()
    with patch.object(client, "chat_json") as mock_chat:
        enrich_scan(result, client)
    # Table has comment and all columns have comments → no AI call needed for this table
    mock_chat.assert_not_called()


def test_enrich_endpoint_descriptions():
    result = ScanResult(
        project="test",
        api=ApiSchema(endpoints=[
            Endpoint(
                method="GET", path="/api/users",
                controller="UserController", service="UserService",
            ),
        ]),
    )
    client = _make_client()
    ai_response = {
        "endpoints": [
            {"method": "GET", "path": "/api/users", "description": "사용자 목록 조회"},
        ],
    }
    with patch.object(client, "chat_json", return_value=ai_response):
        enrich_scan(result, client)

    assert result.api.endpoints[0].description == "사용자 목록 조회"


def test_enrich_external_call_descriptions():
    result = ScanResult(
        project="test",
        dependencies=DependencySchema(externalCalls=[
            ExternalCall(
                source="GdalService", type="gdal",
                command="gdal_translate", file="GdalService.java", line=10,
            ),
        ]),
    )
    client = _make_client()
    ai_response = {
        "calls": [
            {"index": 0, "description": "래스터 이미지 형식을 변환한다"},
        ],
    }
    with patch.object(client, "chat_json", return_value=ai_response):
        enrich_scan(result, client)

    assert result.dependencies.externalCalls[0].description == "래스터 이미지 형식을 변환한다"


def test_enrich_scan_with_disabled_client():
    result = ScanResult(
        project="test",
        database=DatabaseSchema(tables=[
            Table(name="users", columns=[
                Column(name="id", type="BIGINT"),
            ]),
        ]),
    )
    client = _make_client()
    client._disabled = True
    with patch.object(client, "chat_json") as mock_chat:
        enrich_scan(result, client)
    mock_chat.assert_not_called()


def test_enrich_scan_ai_returns_none():
    """AI returns None (parse error) → fields stay empty."""
    result = ScanResult(
        project="test",
        database=DatabaseSchema(tables=[
            Table(name="users", columns=[
                Column(name="id", type="BIGINT"),
            ]),
        ]),
    )
    client = _make_client()
    with patch.object(client, "chat_json", return_value=None):
        enrich_scan(result, client)

    assert result.database.tables[0].comment == ""
    assert result.database.tables[0].columns[0].comment == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/ai/test_enrich_scan.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement `enrich_scan.py`**

Create `src/codemap/ai/enrich_scan.py`:

```python
from __future__ import annotations

import logging
import sys
import time

from codemap.ai.client import AiClient
from codemap.models import ScanResult

logger = logging.getLogger(__name__)

_LANG = {"ko": "한국어", "en": "English"}


def enrich_scan(result: ScanResult, client: AiClient) -> None:
    if not client.available:
        return
    _enrich_tables(result, client)
    if not client.available:
        return
    _enrich_endpoints(result, client)
    if not client.available:
        return
    _enrich_external_calls(result, client)


def _enrich_tables(result: ScanResult, client: AiClient) -> None:
    tables_needing_enrichment = [
        t for t in result.database.tables
        if not t.comment or any(not c.comment for c in t.columns)
    ][:50]  # Cap at 50 tables per spec
    if not tables_needing_enrichment:
        return

    lang = _LANG.get(client.language, client.language)
    system = f"당신은 데이터베이스 문서화 전문가입니다. {lang}로 답변하세요. 유효한 JSON만 반환하세요."
    total = len(tables_needing_enrichment)
    start = time.time()

    for i, table in enumerate(tables_needing_enrichment, 1):
        if not client.available:
            return
        _log_progress(f"테이블 '{table.name}' 설명 생성 중... ({i}/{total})")

        fk_map = {fk.column: fk.references for fk in table.foreignKeys}
        col_lines = []
        for col in table.columns:
            parts = f"{col.name} ({col.type}"
            if col.pk:
                parts += ", PK"
            fk_ref = fk_map.get(col.name)
            if fk_ref:
                parts += f", FK→{fk_ref}"
            parts += ")"
            col_lines.append(f"- {parts}")

        user = (
            f"다음 테이블의 설명을 생성하세요.\n\n"
            f"테이블명: {table.name}\n"
            f"컬럼:\n" + "\n".join(col_lines) + "\n\n"
            f'JSON 형식으로 답변:\n'
            f'{{"table_comment": "테이블 설명", "columns": {{"col_name": "컬럼 설명"}}}}'
        )

        data = client.chat_json(system, user)
        if not data:
            continue

        if not table.comment and "table_comment" in data:
            table.comment = data["table_comment"]

        columns_map = data.get("columns", {})
        for col in table.columns:
            if not col.comment and col.name in columns_map:
                col.comment = columns_map[col.name]

    elapsed = time.time() - start
    _log_progress(f"테이블 설명 생성 완료 ({total}개, {elapsed:.1f}초)", final=True)


def _enrich_endpoints(result: ScanResult, client: AiClient) -> None:
    endpoints = result.api.endpoints
    if not endpoints:
        return

    lang = _LANG.get(client.language, client.language)
    system = f"당신은 API 문서화 전문가입니다. {lang}로 답변하세요. 유효한 JSON만 반환하세요."

    batch_size = 10
    total = len(endpoints)
    start = time.time()

    for batch_start in range(0, total, batch_size):
        if not client.available:
            return
        batch = endpoints[batch_start:batch_start + batch_size]
        batch_end = min(batch_start + batch_size, total)
        _log_progress(f"API 엔드포인트 설명 생성 중... ({batch_end}/{total})")

        lines = []
        for j, ep in enumerate(batch, 1):
            params_str = ", ".join(f"{p.name}: {p.type}" for p in ep.params)
            req_str = ", ".join(f"{f.name}: {f.type}" for f in ep.requestFields)
            lines.append(
                f"{j}. {ep.method} {ep.path} (controller: {ep.controller}, service: {ep.service})\n"
                f"   params: [{params_str}], request: [{req_str}]"
            )

        user = (
            "다음 API 엔드포인트들의 용도를 한 줄로 설명하세요.\n\n"
            + "\n".join(lines) + "\n\n"
            'JSON 형식으로 답변:\n'
            '{"endpoints": [{"path": "...", "method": "...", "description": "..."}]}'
        )

        data = client.chat_json(system, user)
        if not data:
            continue

        ep_descs = {(e["method"], e["path"]): e["description"] for e in data.get("endpoints", [])}
        for ep in batch:
            desc = ep_descs.get((ep.method, ep.path), "")
            if desc:
                ep.description = desc

    elapsed = time.time() - start
    _log_progress(f"API 설명 생성 완료 ({total}개, {elapsed:.1f}초)", final=True)


def _enrich_external_calls(result: ScanResult, client: AiClient) -> None:
    calls = result.dependencies.externalCalls
    if not calls:
        return

    lang = _LANG.get(client.language, client.language)
    system = f"당신은 소프트웨어 문서화 전문가입니다. {lang}로 답변하세요. 유효한 JSON만 반환하세요."

    _log_progress(f"외부 호출 설명 생성 중... ({len(calls)}개)")
    start = time.time()

    lines = []
    for i, ec in enumerate(calls):
        lines.append(f'{i + 1}. type={ec.type}, command="{ec.command}", source={ec.source}')

    user = (
        "다음 외부 프로세스 호출들의 목적을 한 줄로 설명하세요.\n\n"
        + "\n".join(lines) + "\n\n"
        'JSON 형식으로 답변:\n'
        '{"calls": [{"index": 0, "description": "..."}]}'
    )

    data = client.chat_json(system, user)
    if not data:
        return

    for item in data.get("calls", []):
        idx = item.get("index", -1)
        if 0 <= idx < len(calls):
            calls[idx].description = item.get("description", "")

    elapsed = time.time() - start
    _log_progress(f"외부 호출 설명 생성 완료 ({len(calls)}개, {elapsed:.1f}초)", final=True)


def _log_progress(msg: str, final: bool = False) -> None:
    print(f"AI: {msg}", file=sys.stderr, end="\n" if final else "\r", flush=True)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/ai/test_enrich_scan.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/codemap/ai/enrich_scan.py tests/ai/test_enrich_scan.py
git commit -m "feat: add scan enrichment with table, endpoint, and external call descriptions"
```

---

### Task 5: Doc Enrichment Helpers — `enrich_doc.py`

**Files:**
- Create: `src/codemap/ai/enrich_doc.py`
- Create: `tests/ai/test_enrich_doc.py`

- [ ] **Step 1: Write tests for doc enrichment helpers**

Create `tests/ai/test_enrich_doc.py`:

```python
from unittest.mock import patch
from codemap.models import (
    ScanResult, DatabaseSchema, Table, Column, ForeignKey,
    ApiSchema, Endpoint, DependencySchema,
)
from codemap.ai.client import AiClient
from codemap.ai.enrich_doc import (
    generate_table_relationships,
    generate_business_logic,
    generate_overview_narrative,
)


def _make_client():
    return AiClient("http://localhost:11434", "qwen3:30b", "ko")


def test_generate_table_relationships():
    db = DatabaseSchema(tables=[
        Table(name="users", columns=[
            Column(name="id", type="BIGINT", pk=True),
        ]),
        Table(name="orders", columns=[
            Column(name="id", type="BIGINT", pk=True),
            Column(name="user_id", type="BIGINT"),
        ], foreignKeys=[ForeignKey(column="user_id", references="users.id")]),
    ])
    client = _make_client()
    ai_text = "- `orders` 테이블은 `users` 테이블과 다대일 관계이다."
    with patch.object(client, "chat", return_value=ai_text):
        result = generate_table_relationships(db, client)
    assert "orders" in result
    assert "users" in result


def test_generate_table_relationships_no_fks():
    db = DatabaseSchema(tables=[
        Table(name="logs", columns=[Column(name="id", type="BIGINT")]),
    ])
    client = _make_client()
    result = generate_table_relationships(db, client)
    assert result == ""


def test_generate_business_logic():
    ep = Endpoint(
        method="POST", path="/api/users",
        controller="UserController", service="UserService",
        calls=["UserRepository.save", "EmailService.sendWelcome"],
    )
    client = _make_client()
    ai_text = "사용자 정보를 저장하고 환영 이메일을 발송한다."
    with patch.object(client, "chat", return_value=ai_text):
        result = generate_business_logic(ep, client)
    assert "사용자" in result


def test_generate_overview_narrative():
    scan = ScanResult(
        project="my-project",
        database=DatabaseSchema(tables=[
            Table(name="users", columns=[]),
            Table(name="orders", columns=[]),
        ]),
        api=ApiSchema(endpoints=[
            Endpoint(method="GET", path="/api/users",
                     controller="UserController", service="UserService"),
        ]),
    )
    client = _make_client()
    ai_text = "my-project는 사용자와 주문을 관리하는 웹 애플리케이션이다."
    with patch.object(client, "chat", return_value=ai_text):
        result = generate_overview_narrative(scan, client)
    assert "my-project" in result


def test_generate_overview_narrative_disabled_client():
    scan = ScanResult(project="test")
    client = _make_client()
    client._disabled = True
    result = generate_overview_narrative(scan, client)
    assert result == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/ai/test_enrich_doc.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement `enrich_doc.py`**

Create `src/codemap/ai/enrich_doc.py`:

```python
from __future__ import annotations

from codemap.ai.client import AiClient
from codemap.models import DatabaseSchema, Endpoint, ScanResult

_LANG = {"ko": "한국어", "en": "English"}


def generate_table_relationships(db: DatabaseSchema, client: AiClient) -> str:
    all_fks = []
    fk_table_names: set[str] = set()
    for table in db.tables:
        for fk in table.foreignKeys:
            all_fks.append(f"- {table.name}.{fk.column} → {fk.references}")
            fk_table_names.add(table.name)
            # Extract referenced table name (format: "table.column")
            ref_table = fk.references.split(".")[0] if "." in fk.references else fk.references
            fk_table_names.add(ref_table)
    if not all_fks:
        return ""
    if not client.available:
        return ""

    lang = _LANG.get(client.language, client.language)
    # For large DBs (50+ tables), only include tables involved in FK relationships
    if len(db.tables) > 50:
        table_names = ", ".join(sorted(fk_table_names))
    else:
        table_names = ", ".join(t.name for t in db.tables)
    system = f"당신은 데이터베이스 아키텍트입니다. {lang}로 답변하세요."
    user = (
        "다음 테이블 간 FK 관계를 분석하여 자연어로 요약하세요.\n\n"
        f"테이블 목록: {table_names}\n"
        f"FK 관계:\n" + "\n".join(all_fks) + "\n\n"
        "마크다운 bullet list로 관계를 설명하세요."
    )
    return client.chat(system, user)


def generate_business_logic(endpoint: Endpoint, client: AiClient) -> str:
    if not client.available:
        return ""

    lang = _LANG.get(client.language, client.language)
    system = f"당신은 백엔드 개발 문서화 전문가입니다. {lang}로 답변하세요."

    params_str = ", ".join(f"{p.name}({p.type})" for p in endpoint.params)
    req_str = ", ".join(f"{f.name}({f.type})" for f in endpoint.requestFields)
    resp_str = ", ".join(f"{f.name}({f.type})" for f in endpoint.responseFields)

    user = (
        f"다음 API의 비즈니스 로직을 2-3문장으로 설명하세요.\n\n"
        f"엔드포인트: {endpoint.method} {endpoint.path}\n"
        f"컨트롤러: {endpoint.controller}\n"
        f"서비스: {endpoint.service}\n"
        f"호출 체인: {', '.join(endpoint.calls)}\n"
        f"요청 파라미터: {params_str}\n"
        f"요청 필드: {req_str}\n"
        f"응답 필드: {resp_str}"
    )
    return client.chat(system, user)


def generate_overview_narrative(scan: ScanResult, client: AiClient) -> str:
    if not client.available:
        return ""

    lang = _LANG.get(client.language, client.language)
    system = f"당신은 기술 문서 작성 전문가입니다. {lang}로 답변하세요."

    top_tables = ", ".join(t.name for t in scan.database.tables[:10])
    top_paths = ", ".join(ep.path for ep in scan.api.endpoints[:10])

    user = (
        f"다음 프로젝트 스캔 결과를 바탕으로 프로젝트 개요를 3-5문장으로 작성하세요.\n\n"
        f"프로젝트명: {scan.project}\n"
        f"테이블 수: {len(scan.database.tables)}, 주요 테이블: {top_tables}\n"
        f"API 엔드포인트 수: {len(scan.api.endpoints)}, 주요 경로: {top_paths}\n"
        f"외부 호출 수: {len(scan.dependencies.externalCalls)}\n"
        f"프론트엔드 컴포넌트 수: {len(scan.frontend.components)}"
    )
    return client.chat(system, user)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/ai/test_enrich_doc.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/codemap/ai/enrich_doc.py tests/ai/test_enrich_doc.py
git commit -m "feat: add doc enrichment helpers for relationships, business logic, overview"
```

---

### Task 6: Integrate AI into Doc Generators

**Files:**
- Modify: `src/codemap/doc/table_spec.py`
- Modify: `src/codemap/doc/api_spec.py`
- Modify: `src/codemap/doc/overview.py`
- Modify: `tests/doc/test_table_spec.py`
- Modify: `tests/doc/test_api_spec.py`
- Modify: `tests/doc/test_overview.py`

- [ ] **Step 1: Write tests for table_spec with AI**

In `tests/doc/test_table_spec.py`, add:

```python
from unittest.mock import MagicMock


def test_table_spec_with_ai_relationships():
    from codemap.doc.table_spec import generate_table_spec
    db = _sample_db()
    mock_client = MagicMock()
    mock_client.available = True
    mock_client.chat.return_value = "- `users`는 `departments`와 다대일 관계이다."
    md = generate_table_spec(db, ai_client=mock_client)
    assert "## 관계 요약" in md
    assert "departments" in md


def test_table_spec_without_ai_unchanged():
    from codemap.doc.table_spec import generate_table_spec
    md = generate_table_spec(_sample_db())
    assert "## 관계 요약" not in md
```

- [ ] **Step 2: Write tests for api_spec with AI**

In `tests/doc/test_api_spec.py`, add tests. First read the existing test file for the existing `_sample_api` helper:

```python
from unittest.mock import MagicMock


def test_api_spec_with_ai_business_logic():
    from codemap.doc.api_spec import generate_api_spec
    from codemap.models import ApiSchema, Endpoint
    api = ApiSchema(endpoints=[
        Endpoint(method="GET", path="/api/users",
                 controller="UserController", service="UserService"),
    ])
    mock_client = MagicMock()
    mock_client.available = True
    mock_client.chat.return_value = "사용자 목록을 조회하여 반환한다."
    md = generate_api_spec(api, ai_client=mock_client)
    assert "비즈니스 로직" in md


def test_api_spec_without_ai_unchanged():
    from codemap.doc.api_spec import generate_api_spec
    from codemap.models import ApiSchema, Endpoint
    api = ApiSchema(endpoints=[
        Endpoint(method="GET", path="/api/users",
                 controller="UserController", service="UserService"),
    ])
    md = generate_api_spec(api)
    assert "비즈니스 로직" not in md
```

- [ ] **Step 3: Write tests for overview with AI**

In `tests/doc/test_overview.py`, add:

```python
from unittest.mock import MagicMock


def test_overview_with_ai_narrative():
    from codemap.doc.overview import generate_overview
    from codemap.models import ScanResult
    scan = ScanResult(project="test-project")
    mock_client = MagicMock()
    mock_client.available = True
    mock_client.chat.return_value = "test-project는 사용자를 관리하는 시스템이다."
    md = generate_overview(scan, ai_client=mock_client)
    assert "test-project는 사용자를 관리하는 시스템이다." in md


def test_overview_without_ai_unchanged():
    from codemap.doc.overview import generate_overview
    from codemap.models import ScanResult
    scan = ScanResult(project="test-project")
    md = generate_overview(scan)
    assert "# 프로젝트 개요" in md
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `pytest tests/doc/ -v -k "ai"`
Expected: FAIL

- [ ] **Step 5: Modify `table_spec.py` to accept `ai_client`**

Update `src/codemap/doc/table_spec.py`:

```python
from __future__ import annotations

from codemap.models import DatabaseSchema


def generate_table_spec(db: DatabaseSchema, ai_client=None) -> str:
    lines: list[str] = ["# 테이블 정의서", ""]

    # AI: 관계 요약
    if ai_client is not None and ai_client.available:
        from codemap.ai.enrich_doc import generate_table_relationships
        rel = generate_table_relationships(db, ai_client)
        if rel:
            lines.append("## 관계 요약")
            lines.append("")
            lines.append(rel)
            lines.append("")

    # Build FK lookup per table
    for table in db.tables:
        fk_map: dict[str, str] = {}
        for fk in table.foreignKeys:
            fk_map[fk.column] = fk.references

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

- [ ] **Step 6: Modify `api_spec.py` to accept `ai_client`**

Update `src/codemap/doc/api_spec.py` — add `ai_client=None` parameter, and after the endpoint metadata section, add business logic:

```python
from __future__ import annotations

from codemap.models import ApiSchema, Endpoint


def generate_api_spec(api: ApiSchema, ai_client=None) -> str:
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

        # AI: 비즈니스 로직
        if ai_client is not None and ai_client.available:
            from codemap.ai.enrich_doc import generate_business_logic
            logic = generate_business_logic(ep, ai_client)
            if logic:
                lines.append("### 비즈니스 로직")
                lines.append("")
                lines.append(logic)
                lines.append("")

        lines.append("---")
        lines.append("")

    return "\n".join(lines)
```

- [ ] **Step 7: Modify `overview.py` to accept `ai_client`**

Update `src/codemap/doc/overview.py`:

```python
from __future__ import annotations

from codemap.models import ScanResult


def generate_overview(scan: ScanResult, ai_client=None) -> str:
    lines: list[str] = ["# 프로젝트 개요", ""]

    # AI: 자연어 요약
    if ai_client is not None and ai_client.available:
        from codemap.ai.enrich_doc import generate_overview_narrative
        narrative = generate_overview_narrative(scan, ai_client)
        if narrative:
            lines.append(narrative)
            lines.append("")

    lines.append(f"- **프로젝트명:** {scan.project}")
    lines.append(f"- **스캔 일시:** {scan.scannedAt}")
    lines.append("")

    lines.append("## 데이터베이스")
    lines.append(f"- 테이블 수: {len(scan.database.tables)}")
    lines.append("")

    lines.append("## API")
    lines.append(f"- 엔드포인트 수: {len(scan.api.endpoints)}")
    lines.append("")

    lines.append("## 외부 호출")
    lines.append(f"- 외부 프로세스 호출 수: {len(scan.dependencies.externalCalls)}")
    lines.append("")

    return "\n".join(lines)
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `pytest tests/doc/ -v`
Expected: ALL PASS (both old and new tests)

- [ ] **Step 9: Commit**

```bash
git add src/codemap/doc/table_spec.py src/codemap/doc/api_spec.py src/codemap/doc/overview.py tests/doc/
git commit -m "feat: integrate AI enrichment into doc generators"
```

---

### Task 7: CLI Integration — `--no-ai` Flag and Wiring

**Files:**
- Modify: `src/codemap/cli.py:32-49` (main group)
- Modify: `src/codemap/cli.py:52-74` (scan command)
- Modify: `src/codemap/cli.py:142-177` (doc command)
- Modify: `src/codemap/cli.py:254-327` (generate command)
- Test: `tests/test_cli.py`

- [ ] **Step 1: Read existing CLI tests**

Read `tests/test_cli.py` to understand the current testing approach.

- [ ] **Step 2: Write tests for `--no-ai` flag**

In `tests/test_cli.py`, add tests (adjust to match existing test patterns):

```python
def test_main_no_ai_flag(cli_runner):
    """--no-ai flag is accepted and stored in ctx."""
    result = cli_runner.invoke(main, ["--no-ai", "--help"])
    assert result.exit_code == 0
```

- [ ] **Step 3: Add `--no-ai` to main group**

In `src/codemap/cli.py`, modify the `main` function:

```python
@click.group()
@click.version_option(version=__version__)
@click.option("-v", "--verbose", is_flag=True, help="Verbose output")
@click.option("-q", "--quiet", is_flag=True, help="Quiet output")
@click.option("--debug", is_flag=True, help="Debug output")
@click.option("--no-ai", is_flag=True, help="Disable AI enrichment")
@click.pass_context
def main(ctx, verbose, quiet, debug, no_ai):
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
    ctx.obj["no_ai"] = no_ai
```

- [ ] **Step 4: Add AI client helper function**

In `src/codemap/cli.py`, add a helper after `_write_output`:

```python
def _create_ai_client(ctx, config):
    """Create AiClient if AI is enabled, else return None."""
    if ctx.obj.get("no_ai"):
        return None
    if not config.ai.enabled:
        return None
    from codemap.ai.client import AiClient
    return AiClient(config.ai.base_url, config.ai.model, config.ai.language)
```

- [ ] **Step 5: Wire AI into `scan` command**

Modify the `scan` function in `src/codemap/cli.py` to call `enrich_scan` after `run_scan`:

```python
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

    # AI enrichment
    ai_client = _create_ai_client(ctx, config)
    if ai_client:
        from codemap.ai.enrich_scan import enrich_scan
        enrich_scan(result, ai_client)

    json_str = json.dumps(result.model_dump(mode="json", by_alias=True), indent=2, ensure_ascii=False)
    if output:
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).write_text(json_str, encoding="utf-8")
        if not ctx.obj.get("quiet"):
            click.echo(f"Scan result saved to {output}", err=True)
    else:
        click.echo(json_str)
```

- [ ] **Step 6: Wire AI into `doc` command**

Modify `_generate_doc` and `doc` in `src/codemap/cli.py`:

```python
def _generate_doc(scan: ScanResult, doc_type: str, ai_client=None) -> str:
    """Generate a single document type."""
    if doc_type == "table-spec":
        from codemap.doc.table_spec import generate_table_spec
        return generate_table_spec(scan.database, ai_client=ai_client)
    elif doc_type == "api-spec":
        from codemap.doc.api_spec import generate_api_spec
        return generate_api_spec(scan.api, ai_client=ai_client)
    elif doc_type == "overview":
        from codemap.doc.overview import generate_overview
        return generate_overview(scan, ai_client=ai_client)
    return ""
```

Update the `doc` command to create an AI client and pass it:

```python
@main.command()
@click.argument("doc_type", type=click.Choice(_DOC_TYPES))
@click.option("--from", "from_file", required=True, type=click.Path(exists=True), help="Scan JSON file")
@click.option("-o", "--output", type=click.Path(), help="Output file or directory (for 'all')")
@click.pass_context
def doc(ctx, doc_type, from_file, output):
    """Generate markdown documents from scan JSON."""
    scan_result = _load_scan_result(Path(from_file))
    quiet = ctx.obj.get("quiet", False)

    ai_client = None
    if not ctx.obj.get("no_ai"):
        config = load_config(Path("."))
        ai_client = _create_ai_client(ctx, config)

    if doc_type == "all":
        out_dir = Path(output) if output else Path(".")
        out_dir.mkdir(parents=True, exist_ok=True)
        for dt in ["table-spec", "api-spec", "overview"]:
            content = _generate_doc(scan_result, dt, ai_client)
            out_file = out_dir / f"{dt}.md"
            out_file.write_text(content, encoding="utf-8")
        if not quiet:
            click.echo(f"Documents saved to {out_dir}", err=True)
    else:
        content = _generate_doc(scan_result, doc_type, ai_client)
        _write_output(content, output, quiet, "Document")
```

- [ ] **Step 7: Wire AI into `generate` command**

Modify the `generate` function:

```python
@main.command()
@click.argument("path", type=click.Path(exists=True))
@click.option("-o", "--output", required=True, type=click.Path(), help="Output directory")
@click.option("--target", default="all", help="Scan target: db,api,deps,frontend,all")
@click.option("--format", "fmt", default="mermaid", type=click.Choice(["mermaid", "drawio", "all"]))
@click.option("--export", "export_fmt", default="", help="Export format: xlsx,pdf,docx,all")
@click.pass_context
def generate(ctx, path, output, target, fmt, export_fmt):
    """Full pipeline: scan → render → doc → export."""
    from codemap.scanner import run_scan

    project_path = Path(path)
    out_dir = Path(output)
    out_dir.mkdir(parents=True, exist_ok=True)
    quiet = ctx.obj.get("quiet", False)
    config = load_config(project_path)
    targets = set(target.split(","))

    # 1. Scan
    result = run_scan(project_path, config, targets)

    # 1.5 AI enrichment on scan result
    ai_client = _create_ai_client(ctx, config)
    if ai_client:
        from codemap.ai.enrich_scan import enrich_scan
        enrich_scan(result, ai_client)

    scan_file = out_dir / "scan.json"
    json_str = json.dumps(result.model_dump(mode="json", by_alias=True), indent=2, ensure_ascii=False)
    scan_file.write_text(json_str, encoding="utf-8")

    # 2. Render diagrams
    diagram_dir = out_dir / "diagrams"
    diagram_dir.mkdir(exist_ok=True)
    formats = ["mermaid", "drawio"] if fmt == "all" else [fmt]
    for render_fmt in formats:
        ext = ".mmd" if render_fmt == "mermaid" else ".drawio"
        for dt in ["erd", "sequence", "architecture", "component"]:
            content = _render_single(result, dt, render_fmt, [], "")
            (diagram_dir / f"{dt}{ext}").write_text(content, encoding="utf-8")

    # 3. Generate docs (with AI)
    docs_dir = out_dir / "docs"
    docs_dir.mkdir(exist_ok=True)
    for dt in ["table-spec", "api-spec", "overview"]:
        content = _generate_doc(result, dt, ai_client)
        (docs_dir / f"{dt}.md").write_text(content, encoding="utf-8")

    # 4. Export if requested
    if export_fmt:
        export_formats = ["xlsx", "pdf", "docx"] if export_fmt == "all" else export_fmt.split(",")
        export_dir = out_dir / "exports"
        export_dir.mkdir(exist_ok=True)

        for ef in export_formats:
            ef = ef.strip()
            if ef == "xlsx":
                from codemap.export.xlsx import export_table_spec_xlsx, export_api_spec_xlsx
                export_table_spec_xlsx(result, export_dir / "table-spec.xlsx")
                export_api_spec_xlsx(result, export_dir / "api-spec.xlsx")
            elif ef == "pdf":
                try:
                    from codemap.export.pdf import export_pdf
                    css_path = _resolve_template("minimal")
                    export_pdf(docs_dir, export_dir / "report.pdf", css_path=css_path)
                except ImportError:
                    if not quiet:
                        click.echo("PDF export skipped (weasyprint not installed)", err=True)
            elif ef == "docx":
                try:
                    from codemap.export.docx_export import export_docx
                    export_docx(docs_dir, export_dir / "report.docx")
                except ImportError:
                    if not quiet:
                        click.echo("Word export skipped (python-docx not installed)", err=True)

    if not quiet:
        click.echo(f"Generated output in {out_dir}", err=True)
```

- [ ] **Step 8: Wire AI into `export_cmd` auto-chain path**

The `export_cmd` has a JSON→doc auto-chain path for PDF and DOCX. Update it to pass `ai_client` so AI enrichment is consistent across all commands.

In `src/codemap/cli.py`, modify `export_cmd` to create an AI client and pass it to `_generate_doc`:

```python
@main.command(name="export")
@click.argument("format_type", type=click.Choice(["xlsx", "pdf", "docx"]))
@click.option("--from", "from_file", required=True, type=click.Path(exists=True), help="Scan JSON file or docs directory")
@click.option("--type", "doc_type", default="table-spec", help="Document type for xlsx export")
@click.option("--template", default="minimal", help="Template name for PDF")
@click.option("-o", "--output", required=True, type=click.Path(), help="Output file")
@click.pass_context
def export_cmd(ctx, format_type, from_file, doc_type, template, output):
    """Export to xlsx, pdf, or docx format."""
    from_path = Path(from_file)
    out_path = Path(output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    quiet = ctx.obj.get("quiet", False)

    # Create AI client for auto-chain paths
    ai_client = None
    if from_path.suffix == ".json" and not ctx.obj.get("no_ai"):
        config = load_config(Path("."))
        ai_client = _create_ai_client(ctx, config)

    if format_type == "xlsx":
        scan_result = _load_scan_result(from_path)
        from codemap.export.xlsx import export_table_spec_xlsx, export_api_spec_xlsx
        if doc_type == "api-spec":
            export_api_spec_xlsx(scan_result, out_path)
        else:
            export_table_spec_xlsx(scan_result, out_path)

    elif format_type == "pdf":
        from codemap.export.pdf import export_pdf
        if from_path.suffix == ".json":
            scan_result = _load_scan_result(from_path)
            import tempfile
            with tempfile.TemporaryDirectory() as tmp:
                tmp_dir = Path(tmp)
                for dt in ["table-spec", "api-spec", "overview"]:
                    content = _generate_doc(scan_result, dt, ai_client)
                    (tmp_dir / f"{dt}.md").write_text(content, encoding="utf-8")
                css_path = _resolve_template(template)
                export_pdf(tmp_dir, out_path, css_path=css_path)
        else:
            css_path = _resolve_template(template)
            export_pdf(from_path, out_path, css_path=css_path)

    elif format_type == "docx":
        from codemap.export.docx_export import export_docx
        if from_path.suffix == ".json":
            scan_result = _load_scan_result(from_path)
            import tempfile
            with tempfile.TemporaryDirectory() as tmp:
                tmp_dir = Path(tmp)
                for dt in ["table-spec", "api-spec", "overview"]:
                    content = _generate_doc(scan_result, dt, ai_client)
                    (tmp_dir / f"{dt}.md").write_text(content, encoding="utf-8")
                export_docx(tmp_dir, out_path)
        else:
            export_docx(from_path, out_path)

    if not quiet:
        click.echo(f"Exported to {output}", err=True)
```

- [ ] **Step 9: Run tests to verify they pass**

Run: `pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 10: Commit**

```bash
git add src/codemap/cli.py tests/test_cli.py
git commit -m "feat: add --no-ai flag and wire AI enrichment into CLI commands"
```

---

### Task 8: Full Integration Test

**Files:**
- Modify: `tests/test_integration.py`

- [ ] **Step 1: Read existing integration tests**

Read `tests/test_integration.py` to understand the current pattern.

- [ ] **Step 2: Write integration test with AI disabled**

Add to `tests/test_integration.py`:

```python
def test_full_pipeline_no_ai(tmp_path):
    """Full pipeline with --no-ai should work identically to before."""
    runner = CliRunner()
    out_dir = tmp_path / "output"
    result = runner.invoke(main, [
        "--no-ai", "generate", str(FIXTURE_DIR),
        "-o", str(out_dir), "--target", "db",
    ])
    assert result.exit_code == 0
    assert (out_dir / "scan.json").exists()
    assert (out_dir / "docs" / "table-spec.md").exists()
```

- [ ] **Step 3: Run all tests**

Run: `pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_integration.py
git commit -m "test: add integration test for --no-ai pipeline"
```
