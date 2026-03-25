# LLM 연동 설계 — 스캔 결과 보강 & 문서 생성 품질 향상

## 개요

Codemap의 기존 파이프라인(scan → render → doc → export)에 LLM enrichment 레이어를 추가한다.
자체 Ollama 서버(OpenAI 호환 API)를 활용하여 스캔 결과의 빈 설명을 자동 생성하고,
문서 생성 시 자연어 요약과 관계 설명을 보강한다.

- LLM 보강은 **기본 활성화**, `--no-ai` 플래그로 비활성화
- AI 서버 연결 실패 시 warning 로그 후 `--no-ai`와 동일하게 동작 (graceful degradation)
- 첫 번째 호출에서 연결 실패 감지 시 해당 세션의 나머지 AI 호출도 전부 스킵
- timeout 오류는 1회 재시도 후 실패 시 비활성화, connection refused는 즉시 비활성화

## 인프라

- **서버**: Ollama v0.18.0 (`http://183.101.208.30:63001`)
- **API**: OpenAI 호환 `/v1/chat/completions`
- **인증**: 불필요 (Ollama 직접 연결)
- **사용 가능 모델**:
  - `qwen3:30b-a3b-instruct-2507-fp16` (기본값, 고품질)
  - `qwen3:30b-a3b-instruct-2507-q4_K_M` (양자화, 가벼움)
  - `qwen3.5:9b`, `qwen3.5:35b`
  - `nemotron-3-nano:30b`

## 설정

`CodemapConfig`에 `ai` 섹션 추가:

```python
class AiConfig(BaseModel):
    enabled: bool = True
    base_url: str = "http://183.101.208.30:63001"
    model: str = "qwen3:30b-a3b-instruct-2507-fp16"
    language: str = "ko"   # ko / en

class CodemapConfig(BaseModel):
    project: ProjectConfig = Field(default_factory=ProjectConfig)
    scan: ScanConfig = Field(default_factory=ScanConfig)
    export: ExportConfig = Field(default_factory=ExportConfig)
    ai: AiConfig = Field(default_factory=AiConfig)  # 기본값 포함
```

config.yaml 예시:

```yaml
ai:
  enabled: true
  base_url: "http://183.101.208.30:63001"
  model: "qwen3:30b-a3b-instruct-2507-fp16"
  language: "ko"
```

## 모듈 구조

```
src/codemap/ai/
├── __init__.py          # AiConfig 모델 export, create_client 헬퍼
├── client.py            # OpenAI 호환 HTTP 클라이언트
├── enrich_scan.py       # 스캔 결과 보강 (기능 1,2,3)
└── enrich_doc.py        # doc 함수에서 호출하는 AI 보강 헬퍼 (기능 4,5,6)
```

## AI 클라이언트 (`client.py`)

Python 표준 라이브러리 `urllib.request`만 사용하여 외부 의존성을 추가하지 않는다.

```python
class AiClient:
    def __init__(self, base_url: str, model: str, language: str = "ko"):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.language = language
        self._disabled = False  # 연결 실패 시 True로 전환

    def chat(self, system: str, user: str, temperature: float = 0.3) -> str:
        """POST /v1/chat/completions → 응답 텍스트 반환.
        요청 body에 stream: false 명시.
        연결 실패 시 warning 로그 + 빈 문자열 반환 + _disabled 설정."""

    def chat_json(self, system: str, user: str, temperature: float = 0.3) -> dict | None:
        """chat() 호출 후 JSON 파싱.
        - markdown 코드 펜스(```json ... ```) 자동 제거
        - json.loads() 실패 시 warning 후 None 반환"""

    @property
    def available(self) -> bool:
        """클라이언트가 사용 가능한 상태인지 (연결 실패로 비활성화되지 않았는지)"""
        return not self._disabled
```

- 타임아웃: 120초 (대형 프로젝트 대비)
- 요청 body에 `"stream": false` 명시 (Ollama 기본이 streaming이므로)
- **에러 처리 전략**:
  - `ConnectionRefusedError` → 즉시 `_disabled = True`
  - `TimeoutError` → 1회 재시도 후 실패 시 `_disabled = True`
  - `HTTP 5xx` → 1회 재시도 후 실패 시 `_disabled = True`
  - JSON 파싱 실패 → warning 후 해당 항목만 스킵 (클라이언트 비활성화하지 않음)
- `--verbose` 모드에서 각 LLM 호출마다 INFO 로그 (대상 항목명, 응답 시간)

## 스캔 결과 보강 (`enrich_scan.py`)

`scan` 이후 `ScanResult`를 받아서 LLM으로 빈 설명을 채운다.

```python
def enrich_scan(result: ScanResult, client: AiClient) -> ScanResult:
    """ScanResult를 받아 AI로 보강한 결과를 반환 (in-place 수정)."""
```

### 기능 1: 테이블/컬럼 설명 자동 생성

- **대상**: `comment`가 비어있는 테이블과 컬럼
- **처리 단위**: 테이블 하나씩 (테이블명 + 전체 컬럼 목록을 한 번의 호출로)
- **기존 comment가 있는 항목은 건드리지 않음**
- **대형 DB 대응**: 테이블 50개 초과 시 50개 단위로 청킹하여 처리

**프롬프트 템플릿:**

```
System: "당신은 데이터베이스 문서화 전문가입니다. {language}로 답변하세요. 유효한 JSON만 반환하세요."

User: "다음 테이블의 설명을 생성하세요.

테이블명: {table_name}
컬럼:
- {col_name} ({col_type}, PK={pk}, FK→{fk_ref})
- ...

JSON 형식으로 답변:
{
  \"table_comment\": \"테이블 설명\",
  \"columns\": {
    \"col_name\": \"컬럼 설명\",
    ...
  }
}"
```

**응답 JSON 스키마:**

```json
{
  "table_comment": "string",
  "columns": {
    "<column_name>": "string"
  }
}
```

### 기능 2: API 엔드포인트 용도 요약

- **대상**: 모든 엔드포인트
- **입력**: `method`, `path`, `controller`, `service`, `params`, `requestFields`, `responseFields`
- **결과**: 엔드포인트별 한 줄 용도 설명 생성
- **처리 단위**: 엔드포인트 10개씩 배치
- **모델 변경**: `Endpoint`에 `description: str = ""` 필드 추가

**프롬프트 템플릿:**

```
System: "당신은 API 문서화 전문가입니다. {language}로 답변하세요. 유효한 JSON만 반환하세요."

User: "다음 API 엔드포인트들의 용도를 한 줄로 설명하세요.

1. {method} {path} (controller: {controller}, service: {service})
   params: [{param_name}: {param_type}], request: [{field_name}: {field_type}]
2. ...

JSON 형식으로 답변:
{
  \"endpoints\": [
    {\"path\": \"...\", \"method\": \"...\", \"description\": \"...\"},
    ...
  ]
}"
```

**응답 JSON 스키마:**

```json
{
  "endpoints": [
    {"path": "string", "method": "string", "description": "string"}
  ]
}
```

### 기능 3: 외부 호출 목적 설명

- **대상**: 모든 `ExternalCall`
- **입력**: `type`, `command`, `source` 정보
- **결과**: 각 외부 호출의 목적을 한 줄로 생성
- **처리 단위**: 전체를 한 번에 (일반적으로 소수)
- **모델 변경**: `ExternalCall`에 `description: str = ""` 필드 추가

**프롬프트 템플릿:**

```
System: "당신은 소프트웨어 문서화 전문가입니다. {language}로 답변하세요. 유효한 JSON만 반환하세요."

User: "다음 외부 프로세스 호출들의 목적을 한 줄로 설명하세요.

1. type={type}, command=\"{command}\", source={source}
2. ...

JSON 형식으로 답변:
{
  \"calls\": [
    {\"index\": 0, \"description\": \"...\"},
    ...
  ]
}"
```

**응답 JSON 스키마:**

```json
{
  "calls": [
    {"index": 0, "description": "string"}
  ]
}
```

## 문서 생성 보강 (`enrich_doc.py`)

`enrich_doc.py`는 독립적인 파이프라인 단계가 아니라, `generate_*` 함수 내부에서 호출되는 헬퍼 함수 모음이다.

```python
# enrich_doc.py
def generate_table_relationships(db: DatabaseSchema, client: AiClient) -> str:
    """FK 기반 테이블 관계 요약 마크다운 생성"""

def generate_business_logic(endpoint: Endpoint, client: AiClient) -> str:
    """엔드포인트별 비즈니스 로직 요약 생성"""

def generate_overview_narrative(scan: ScanResult, client: AiClient) -> str:
    """프로젝트 개요 자연어 문단 생성"""
```

### 기능 4: 테이블 간 관계 설명 (`table_spec.py`에서 호출)

- FK 정보를 기반으로 테이블 간 관계를 LLM에 전달
- "관계 요약" 섹션을 테이블 정의서 상단에 추가
- 예: "`user_role` 테이블은 `user`와 `role`을 다대다로 연결하는 매핑 테이블이다"
- **대형 DB 대응**: 테이블 50개 초과 시 FK가 있는 테이블만 추출하여 전달

**프롬프트 템플릿:**

```
System: "당신은 데이터베이스 아키텍트입니다. {language}로 답변하세요."

User: "다음 테이블 간 FK 관계를 분석하여 자연어로 요약하세요.

테이블 목록: {table_names}
FK 관계:
- {table}.{column} → {ref_table}.{ref_column}
- ...

마크다운 bullet list로 관계를 설명하세요."
```

### 기능 5: API 비즈니스 로직 요약 (`api_spec.py`에서 호출)

- 각 엔드포인트의 controller → service → calls 흐름을 LLM에 전달
- 엔드포인트별 "비즈니스 로직" 항목 추가
- 기능 2의 `description`보다 상세한 로직 설명

**프롬프트 템플릿:**

```
System: "당신은 백엔드 개발 문서화 전문가입니다. {language}로 답변하세요."

User: "다음 API의 비즈니스 로직을 2-3문장으로 설명하세요.

엔드포인트: {method} {path}
컨트롤러: {controller}
서비스: {service}
호출 체인: {calls}
요청 파라미터: {params}
요청 필드: {requestFields}
응답 필드: {responseFields}"
```

### 기능 6: 프로젝트 개요 자연어 작성 (`overview.py`에서 호출)

- 전체 스캔 결과 요약을 LLM이 자연어로 작성
- 프로젝트 구조, 주요 도메인, 기술 스택 특징, DB 규모, API 특성 포함
- 기존 수치 정보는 유지하되 상단에 자연어 요약 문단 추가

**프롬프트 템플릿:**

```
System: "당신은 기술 문서 작성 전문가입니다. {language}로 답변하세요."

User: "다음 프로젝트 스캔 결과를 바탕으로 프로젝트 개요를 3-5문장으로 작성하세요.

프로젝트명: {project}
테이블 수: {table_count}, 주요 테이블: {top_tables}
API 엔드포인트 수: {endpoint_count}, 주요 경로: {top_paths}
외부 호출 수: {external_count}
프론트엔드 컴포넌트 수: {component_count}"
```

### doc 함수 변경 방식

기존 `generate_*` 함수 시그니처에 `ai_client` 파라미터 추가:

```python
def generate_table_spec(db: DatabaseSchema, ai_client: AiClient | None = None) -> str:
def generate_api_spec(api: ApiSchema, ai_client: AiClient | None = None) -> str:
def generate_overview(scan: ScanResult, ai_client: AiClient | None = None) -> str:
```

`ai_client`가 `None`이면 기존과 동일하게 동작. `ai_client`가 있으면 `enrich_doc.py`의 헬퍼 함수를 호출하여 AI 보강 섹션을 마크다운에 삽입.

## CLI 변경

### `main` 그룹

```python
@click.option("--no-ai", is_flag=True, help="Disable AI enrichment")
def main(ctx, verbose, quiet, debug, no_ai):
    ctx.obj["no_ai"] = no_ai
```

### `scan` 명령

```python
def scan(ctx, path, target, output):
    result = run_scan(project_path, config, targets)
    if not ctx.obj.get("no_ai") and config.ai.enabled:
        from codemap.ai.client import AiClient
        client = AiClient(config.ai.base_url, config.ai.model, config.ai.language)
        from codemap.ai.enrich_scan import enrich_scan
        enrich_scan(result, client)
    # ... JSON 출력
```

### `doc` 명령

```python
def doc(ctx, doc_type, from_file, output):
    scan_result = _load_scan_result(Path(from_file))
    ai_client = None
    if not ctx.obj.get("no_ai"):
        config = load_config(Path("."))
        if config.ai.enabled:
            from codemap.ai.client import AiClient
            ai_client = AiClient(config.ai.base_url, config.ai.model, config.ai.language)
    content = _generate_doc(scan_result, dt, ai_client)
```

### `generate` 명령 (전체 파이프라인)

```
scan → enrich_scan(if ai) → render → doc(with ai_client) → export
```

## 파이프라인 흐름도

```
scan ──→ enrich_scan(ScanResult) ──→ render ──→ doc(ai_client) ──→ export
         │                                      │
         ├─ 기능1: 테이블/컬럼 설명               ├─ 기능4: 테이블 관계 설명 (헬퍼 호출)
         ├─ 기능2: API 엔드포인트 용도             ├─ 기능5: API 비즈니스 로직 (헬퍼 호출)
         └─ 기능3: 외부 호출 목적                 └─ 기능6: 프로젝트 개요 (헬퍼 호출)

         --no-ai 또는 서버 연결 실패 시 → 스킵 (기존 동작과 동일)
```

## 모델 변경 요약

| 모델 | 추가 필드 | 용도 |
|------|----------|------|
| `Endpoint` | `description: str = ""` | API 용도 요약 (기능 2) |
| `ExternalCall` | `description: str = ""` | 외부 호출 목적 (기능 3) |
| `CodemapConfig` | `ai: AiConfig = Field(default_factory=AiConfig)` | AI 설정 |

새 필드는 모두 `= ""` 기본값이므로, 기존 scan.json 파일의 역호환성은 유지된다.

## 의존성

- 외부 패키지 추가 없음 (`urllib.request` 사용)
- 기존 `pyproject.toml` 변경 불필요
