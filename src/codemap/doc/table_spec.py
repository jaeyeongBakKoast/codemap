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
