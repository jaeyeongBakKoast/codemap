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
            ref_table = fk.references.split(".")[0] if "." in fk.references else fk.references
            fk_table_names.add(ref_table)
    if not all_fks:
        return ""
    if not client.available:
        return ""

    lang = _LANG.get(client.language, client.language)
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
