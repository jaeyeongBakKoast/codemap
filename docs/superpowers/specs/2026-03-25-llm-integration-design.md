# LLM 연동 설계 — 스캔 결과 보강 & 문서 생성 품질 향상

## 개요

Codemap의 기존 파이프라인(scan → render → doc → export)에 LLM enrichment 레이어를 추가한다.
자체 Ollama 서버(OpenAI 호환 API)를 활용하여 스캔 결과의 빈 설명을 자동 생성하고,
문서 생성 시 자연어 요약과 관계 설명을 보강한다.

- LLM 보강은 **기본 활성화**, `--no-ai` 플래그로 비활성화
- AI 서버 연결 실패 시 warning 로그 후 `--no-ai`와 동일하게 동작 (graceful degradation)
- 첫 번째 호출에서 연결 실패 감지 시 해당 세션의 나머지 AI 호출도 전부 스킵

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
└── enrich_doc.py        # 문서 생성 보강 (기능 4,5,6)
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
        연결 실패 시 warning 로그 + 빈 문자열 반환 + _disabled 설정."""

    @property
    def available(self) -> bool:
        """클라이언트가 사용 가능한 상태인지 (연결 실패로 비활성화되지 않았는지)"""
        return not self._disabled
```

- 타임아웃: 120초 (대형 프로젝트 대비)
- 연결 실패 시 `_disabled = True`로 설정, 이후 모든 `chat()` 호출은 즉시 빈 문자열 반환
- JSON 응답 파싱 실패 시에도 warning 후 빈 문자열 반환

## 스캔 결과 보강 (`enrich_scan.py`)

`scan` 이후 `ScanResult`를 받아서 LLM으로 빈 설명을 채운다.

### 기능 1: 테이블/컬럼 설명 자동 생성

- **대상**: `comment`가 비어있는 테이블과 컬럼
- **처리 단위**: 테이블 하나씩 (테이블명 + 전체 컬럼 목록을 한 번의 호출로)
- **프롬프트**: 테이블 구조(이름, 컬럼명, 타입, PK/FK 정보)를 전달하고 JSON 형식으로 설명 요청
- **결과**: `Table.comment`와 `Column.comment`에 생성된 설명 주입
- **기존 comment가 있는 항목은 건드리지 않음**

### 기능 2: API 엔드포인트 용도 요약

- **대상**: 모든 엔드포인트
- **입력**: `method`, `path`, `controller`, `service`, `params`, `requestFields`, `responseFields`
- **결과**: 엔드포인트별 한 줄 용도 설명 생성
- **모델 변경**: `Endpoint`에 `description: str = ""` 필드 추가

### 기능 3: 외부 호출 목적 설명

- **대상**: 모든 `ExternalCall`
- **입력**: `type`, `command`, `source` 정보
- **결과**: 각 외부 호출의 목적을 한 줄로 생성
- **모델 변경**: `ExternalCall`에 `description: str = ""` 필드 추가

### 프롬프트 전략

- 여러 항목을 한 번의 API 호출로 배치 처리 (예: 테이블 하나의 전체 컬럼)
- JSON 형식으로 응답을 요청하여 파싱 안정성 확보
- `language` 설정에 따라 시스템 프롬프트에 언어 지시 (예: "한국어로 답변하세요")

## 문서 생성 보강 (`enrich_doc.py`)

`doc` 단계에서 기존 generate 함수에 AI 보강을 추가한다.

### 기능 4: 테이블 간 관계 설명 (`table_spec.py`)

- FK 정보를 기반으로 전체 테이블 목록 + FK 관계를 한 번의 호출로 전달
- "관계 요약" 섹션을 테이블 정의서 상단에 추가
- 예: "`user_role` 테이블은 `user`와 `role`을 다대다로 연결하는 매핑 테이블이다"

### 기능 5: API 비즈니스 로직 요약 (`api_spec.py`)

- 각 엔드포인트의 controller → service → calls 흐름을 LLM에 전달
- 엔드포인트별 "비즈니스 로직" 항목 추가
- 기능 2의 `description`보다 상세한 로직 설명

### 기능 6: 프로젝트 개요 자연어 작성 (`overview.py`)

- 전체 스캔 결과 요약을 LLM이 자연어로 작성
- 프로젝트 구조, 주요 도메인, 기술 스택 특징, DB 규모, API 특성 포함
- 기존 수치 정보는 유지하되 상단에 자연어 요약 문단 추가

### doc 함수 변경 방식

기존 `generate_*` 함수 시그니처에 `ai_client` 파라미터 추가:

```python
def generate_table_spec(db: DatabaseSchema, ai_client: AiClient | None = None) -> str:
def generate_api_spec(api: ApiSchema, ai_client: AiClient | None = None) -> str:
def generate_overview(scan: ScanResult, ai_client: AiClient | None = None) -> str:
```

`ai_client`가 `None`이면 기존과 동일하게 동작.

## CLI 변경

### `main` 그룹

```python
@click.option("--no-ai", is_flag=True, help="Disable AI enrichment")
```

### `scan` 명령

```
scan → run_scan() → ai.enrich_scan(result, client) → JSON 출력
```

### `doc` 명령

```
load scan.json → generate_*(data, ai_client) → markdown 출력
```

### `generate` 명령 (전체 파이프라인)

```
scan → enrich_scan → render → doc(with ai_client) → export
```

## 파이프라인 흐름도

```
scan ──→ enrich_scan(ScanResult) ──→ render/doc ──→ enrich_doc ──→ export
         │                                          │
         ├─ 기능1: 테이블/컬럼 설명                   ├─ 기능4: 테이블 관계 설명
         ├─ 기능2: API 엔드포인트 용도                 ├─ 기능5: API 비즈니스 로직
         └─ 기능3: 외부 호출 목적                     └─ 기능6: 프로젝트 개요

         --no-ai 또는 서버 연결 실패 시 → 스킵 (기존 동작과 동일)
```

## 모델 변경 요약

| 모델 | 추가 필드 | 용도 |
|------|----------|------|
| `Endpoint` | `description: str = ""` | API 용도 요약 (기능 2) |
| `ExternalCall` | `description: str = ""` | 외부 호출 목적 (기능 3) |
| `CodemapConfig` | `ai: AiConfig` | AI 설정 |

## 의존성

- 외부 패키지 추가 없음 (`urllib.request` 사용)
- 기존 `pyproject.toml` 변경 불필요
