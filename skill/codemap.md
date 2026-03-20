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
