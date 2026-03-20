from codemap.models import ApiSchema


def generate_api_spec(api: ApiSchema) -> str:
    lines: list[str] = ["# API 명세서", ""]
    lines.append("| 메서드 | 경로 | 컨트롤러 | 서비스 | 호출 |")
    lines.append("|--------|------|----------|--------|------|")

    for ep in api.endpoints:
        calls = ", ".join(ep.calls)
        lines.append(f"| {ep.method} | {ep.path} | {ep.controller} | {ep.service} | {calls} |")

    lines.append("")
    return "\n".join(lines)
