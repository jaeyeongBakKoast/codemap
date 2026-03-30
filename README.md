# Codemap

코드베이스를 정적 분석하여 구조화된 데이터를 추출하고, 기술 문서를 자동 생성하는 CLI 도구.

LLM(Ollama)을 연동하여 테이블/API 설명을 자동 생성하고, 문서 품질을 보강한다.

## 주요 기능

- **코드베이스 스캔**: SQL DDL, Spring Boot(Java), React(TypeScript), 외부 호출(Shell/Python/GDAL) 정적 분석
- **다이어그램 생성**: ERD, 시퀀스, 아키텍처, 컴포넌트 (Mermaid / draw.io)
- **문서 생성**: 테이블 정의서, API 명세서, 프로젝트 개요 (Markdown)
- **내보내기**: PDF, Word, Excel
- **LLM 보강**: 테이블/컬럼 설명, API 용도 요약, 비즈니스 로직 설명, 프로젝트 개요 자연어 작성
- **제네릭 타입 해석**: `ResultResponse<List<T>>` 같은 중첩 제네릭을 트리 구조로 풀어서 문서화

## 파이프라인

```
코드베이스 ──→ [scan] ──→ [AI 보강] ──→ scan.json
                                          │
                                          ├──→ [render] ──→ .mmd / .drawio
                                          ├──→ [doc]    ──→ .md
                                          └──→ [export] ──→ .pdf / .docx / .xlsx
```

## 설치

```bash
# Python 3.12+ 필요
pip install -e .

# PDF 내보내기 (선택)
pip install -e ".[pdf]"

# Word 내보내기 (선택)
pip install -e ".[docx]"

# 전체
pip install -e ".[all]"
```

## 빠른 시작

```bash
# 전체 파이프라인 실행 (스캔 → 다이어그램 → 문서 → 엑셀)
codemap generate ./my-project -o output/ --export xlsx

# AI 보강 없이 실행
codemap --no-ai generate ./my-project -o output/
```

## LLM 연동 설정

Ollama 또는 OpenAI 호환 API 서버가 필요하다.

### 1. `.env` 파일 생성

```bash
cp .env.example .env
```

```env
CODEMAP_AI_URL=http://localhost:11434
CODEMAP_AI_MODEL=qwen3:30b-a3b-instruct-2507-fp16
```

### 2. 실행

AI 보강은 기본 활성화. 서버 연결 실패 시 자동으로 AI 없이 진행한다.

```bash
# .env 로드 후 실행
export $(cat .env | xargs) && codemap generate ./my-project -o output/
```

### AI 보강 항목

| 단계 | 보강 내용 |
|------|----------|
| **scan** | 테이블/컬럼 설명 자동 생성, API 용도 요약, 외부 호출 목적 설명 |
| **doc** | 테이블 간 관계 요약, API 비즈니스 로직 설명, 프로젝트 개요 자연어 작성 |

### 설정 (`config.yaml`)

```yaml
ai:
  enabled: true
  language: "ko"     # ko / en
```

`base_url`과 `model`은 `.env` 환경변수에서 읽는다 (`CODEMAP_AI_URL`, `CODEMAP_AI_MODEL`).

## CLI 명령어

### `scan` — 코드베이스 분석

```bash
codemap scan <path> [--target db|api|deps|frontend|all] [-o output.json]
```

| target | 분석 대상 |
|--------|----------|
| `db` | SQL DDL/DML → 테이블, 컬럼, FK, 인덱스 |
| `api` | Spring Controller/Service → 엔드포인트, 파라미터, 반환 타입 |
| `deps` | 모듈 의존성 + 외부 호출 (ProcessBuilder, Python, GDAL) |
| `frontend` | React 컴포넌트, API 호출 (axios/fetch) |
| `all` | 전체 (기본값) |

여러 타겟 지정 가능: `--target db,api`

### `render` — 다이어그램 생성

```bash
codemap render <erd|sequence|architecture|component|all> --from scan.json --format <mermaid|drawio> [-o output]
```

시퀀스 다이어그램 전용 옵션:
```bash
codemap render sequence --from scan.json \
  --entries "FileController.upload,GdalService.convert" \
  --label "파일 업로드 및 변환"
```

### `doc` — 마크다운 문서 생성

```bash
codemap doc <table-spec|api-spec|overview|all> --from scan.json [-o output]
```

| 문서 | 내용 |
|------|------|
| `table-spec` | 테이블 정의서 (컬럼, 타입, PK/FK, 인덱스) + AI 관계 요약 |
| `api-spec` | API 명세서 (엔드포인트, 파라미터, 요청/응답 필드) + AI 비즈니스 로직 |
| `overview` | 프로젝트 개요 (수치 + AI 자연어 요약) |

### `export` — 내보내기

```bash
codemap export <xlsx|pdf|docx> --from scan.json -o output [--type table-spec|api-spec]
```

- **xlsx**: scan JSON에서 직접 구조화 데이터로 변환. 응답 필드는 트리 구조로 표시
- **pdf/docx**: 마크다운 디렉토리 또는 scan JSON 모두 가능 (JSON 입력 시 자동 체이닝)

### `generate` — 전체 파이프라인

```bash
codemap generate <path> -o <output/> [--target all] [--format mermaid|drawio|all] [--export xlsx|pdf|docx|all]
```

한 번에 실행: scan → AI 보강 → render → doc → export

### 공통 옵션

```bash
--no-ai       AI 보강 비활성화
-v, --verbose 상세 로그
-q, --quiet   경고 숨기고 결과만 출력
--debug       디버그 로그
```

## 출력 예시

### 테이블 정의서 (Excel)

테이블별 시트에 컬럼 정보가 정리되고, AI가 빈 설명을 자동 채운다.

### API 명세서 (Excel)

엔드포인트별 시트에 파라미터, 요청/응답 필드가 트리 구조로 표시된다:

```
payload: List<CampaignResponse>
  ㄴ campaignId: Integer       (고유번호)
  ㄴ campaignName: String      (이름)
  ㄴ imageList: List<FileData>
    ㄴ id: Long                (고유번호)
    ㄴ fileName: String        (파일 이름)
message: String                (메시지)
```

## 설정 파일

`.codemap/config.yaml` (프로젝트) → `~/.codemap/config.yaml` (글로벌) 순으로 탐색. 없으면 프로젝트 구조를 자동 감지.

```yaml
project:
  name: "my-project"

scan:
  database:
    paths: ["doc/database/**/*.sql"]
  backend:
    paths: ["src/main/java/**/*.java"]
    framework: spring
  frontend:
    paths: ["src/frontend/**/*.{ts,tsx}"]
    framework: react

export:
  template: "corporate"

ai:
  enabled: true
  language: "ko"
```

## 프로젝트 구조

```
src/codemap/
├── cli.py                 # Click CLI 엔트리포인트
├── config.py              # 설정 파일 로드 + 자동 감지
├── models.py              # Pydantic 데이터 모델
├── scanner/
│   ├── sql_scanner.py     # DDL 파싱 (sqlglot)
│   ├── java_scanner.py    # Spring/Java 분석 (tree-sitter)
│   ├── ts_scanner.py      # React/TypeScript 분석 (tree-sitter)
│   └── external_scanner.py # 외부 호출 탐지
├── renderer/
│   ├── mermaid.py         # Mermaid 다이어그램
│   └── drawio.py          # draw.io XML
├── doc/
│   ├── table_spec.py      # 테이블 정의서
│   ├── api_spec.py        # API 명세서
│   └── overview.py        # 프로젝트 개요
├── export/
│   ├── xlsx.py            # Excel (openpyxl)
│   ├── pdf.py             # PDF (weasyprint)
│   └── docx_export.py     # Word (python-docx)
└── ai/
    ├── client.py          # OpenAI 호환 HTTP 클라이언트
    ├── enrich_scan.py     # 스캔 결과 AI 보강
    └── enrich_doc.py      # 문서 생성 AI 보강
```

## 기술 스택

| 라이브러리 | 용도 |
|-----------|------|
| click | CLI 프레임워크 |
| sqlglot | SQL DDL 파싱 |
| tree-sitter + tree-sitter-java | Java/Spring 코드 분석 |
| tree-sitter-typescript | React/TypeScript 코드 분석 |
| pydantic | 데이터 모델 검증 |
| openpyxl | Excel 내보내기 |
| weasyprint (선택) | PDF 내보내기 |
| python-docx (선택) | Word 내보내기 |

## 에러 처리

- SQL 파싱 실패 → 해당 파일 건너뛰고 나머지 계속 처리
- AI 서버 연결 실패 → `--no-ai`와 동일하게 동작 (graceful degradation)
- 지원하지 않는 문법 → 경고 출력 후 가능한 범위에서 처리
- 선택 의존성 미설치 → 설치 안내 메시지 출력

## 라이선스

MIT
