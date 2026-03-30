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
