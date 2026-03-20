from codemap.models import DatabaseSchema


def generate_table_spec(db: DatabaseSchema) -> str:
    lines: list[str] = ["# 테이블 정의서", ""]

    # Build FK lookup per table
    for table in db.tables:
        fk_map: dict[str, str] = {}
        for fk in table.foreignKeys:
            fk_map[fk.column] = fk.references

        lines.append(f"## {table.name}")
        lines.append("")
        lines.append("### 컬럼")
        lines.append("")
        lines.append("| 컬럼명 | 타입 | PK | FK | Nullable | 설명 |")
        lines.append("|--------|------|----|----|----------|------|")

        for col in table.columns:
            pk = "O" if col.pk else ""
            fk = fk_map.get(col.name, "")
            nullable = "O" if col.nullable else "X"
            lines.append(f"| {col.name} | {col.type} | {pk} | {fk} | {nullable} | |")

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
