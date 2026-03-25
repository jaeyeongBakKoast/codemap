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
