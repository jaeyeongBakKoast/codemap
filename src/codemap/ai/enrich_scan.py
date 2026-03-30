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
