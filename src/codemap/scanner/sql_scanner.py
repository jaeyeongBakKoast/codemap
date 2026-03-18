# src/codemap/scanner/sql_scanner.py
from __future__ import annotations

import logging
from pathlib import Path

import sqlglot
from sqlglot import exp

from codemap.models import Table, Column, ForeignKey, Index

logger = logging.getLogger(__name__)


def scan_sql(sql_files: list[Path]) -> list[Table]:
    tables: list[Table] = []
    indexes: dict[str, list[Index]] = {}

    for sql_file in sql_files:
        try:
            sql_text = sql_file.read_text(encoding="utf-8")
            statements = sqlglot.parse(sql_text)
        except Exception as e:
            logger.warning(f"Failed to parse {sql_file}: {e}")
            continue

        for stmt in statements:
            if stmt is None:
                continue
            if isinstance(stmt, exp.Create):
                if stmt.kind == "TABLE":
                    table = _parse_create_table(stmt)
                    if table:
                        tables.append(table)
                elif stmt.kind == "INDEX":
                    idx = _parse_create_index(stmt)
                    if idx:
                        table_name, index = idx
                        indexes.setdefault(table_name, []).append(index)

    # Attach indexes to tables
    for table in tables:
        if table.name in indexes:
            table.indexes.extend(indexes[table.name])

    return tables


def _parse_create_table(stmt: exp.Create) -> Table | None:
    schema_expr = stmt.this
    if not isinstance(schema_expr, exp.Schema):
        return None

    table_name = schema_expr.this.name if schema_expr.this else None
    if not table_name:
        return None

    columns: list[Column] = []
    foreign_keys: list[ForeignKey] = []

    # Collect inline PK columns first
    pk_columns: set[str] = set()
    for col_def in schema_expr.expressions:
        if isinstance(col_def, exp.ColumnDef):
            for _ in col_def.find_all(exp.PrimaryKeyColumnConstraint):
                pk_columns.add(col_def.name)
        elif isinstance(col_def, exp.PrimaryKey):
            for expr in col_def.expressions:
                if hasattr(expr, "name"):
                    pk_columns.add(expr.name)

    for col_def in schema_expr.expressions:
        if isinstance(col_def, exp.ColumnDef):
            col_name = col_def.name
            col_type = col_def.args.get("kind")
            type_str = col_type.sql() if col_type else "UNKNOWN"

            nullable = True
            for _ in col_def.find_all(exp.NotNullColumnConstraint):
                nullable = False

            is_pk = col_name in pk_columns
            if is_pk:
                nullable = False

            columns.append(Column(name=col_name, type=type_str, pk=is_pk, nullable=nullable))

        elif isinstance(col_def, exp.Constraint):
            # Named constraint — unwrap to find ForeignKey
            for sub in col_def.expressions:
                if isinstance(sub, exp.ForeignKey):
                    _extract_foreign_keys(sub, foreign_keys)

        elif isinstance(col_def, exp.ForeignKey):
            _extract_foreign_keys(col_def, foreign_keys)

    return Table(name=table_name, columns=columns, foreignKeys=foreign_keys)


def _extract_foreign_keys(fk_node: exp.ForeignKey, foreign_keys: list[ForeignKey]) -> None:
    """Extract ForeignKey models from a sqlglot ForeignKey expression."""
    fk_cols = [e.name for e in fk_node.expressions if hasattr(e, "name")]
    ref = fk_node.find(exp.Reference)
    if ref and fk_cols:
        # In sqlglot 30, ref.this is a Schema(Table, [col_identifiers])
        ref_inner = ref.this
        if isinstance(ref_inner, exp.Schema):
            ref_table = ref_inner.this.name if ref_inner.this else ""
            ref_cols = [e.name for e in ref_inner.expressions if hasattr(e, "name")]
        else:
            ref_table = ref_inner.name if hasattr(ref_inner, "name") else ""
            ref_cols = [e.name for e in ref.expressions if hasattr(e, "name")]

        for fc, rc in zip(fk_cols, ref_cols if ref_cols else [""]):
            foreign_keys.append(
                ForeignKey(column=fc, references=f"{ref_table}.{rc}" if rc else ref_table)
            )


def _parse_create_index(stmt: exp.Create) -> tuple[str, Index] | None:
    try:
        # UNIQUE flag lives on the Create statement in sqlglot 30
        unique = bool(stmt.args.get("unique"))

        idx_expr = stmt.this  # exp.Index node
        index_name = idx_expr.this.name if hasattr(idx_expr, "this") and idx_expr.this else ""

        # Table name is in idx_expr.args['table']
        table_expr = idx_expr.args.get("table")
        if not table_expr:
            # Fallback search
            table_expr = stmt.find(exp.Table)
        if not table_expr:
            return None
        table_name = table_expr.name

        # Columns live in idx_expr.args['params'].args['columns']
        cols: list[str] = []
        params = idx_expr.args.get("params")
        if params:
            col_list = params.args.get("columns") or []
            for col in col_list:
                # Each entry is Ordered(Column(...)) or Column(...)
                if hasattr(col, "name") and col.name:
                    cols.append(col.name)
                elif hasattr(col, "this") and hasattr(col.this, "name"):
                    cols.append(col.this.name)

        if index_name and table_name and cols:
            return table_name, Index(name=index_name, columns=cols, unique=unique)
    except Exception as e:
        logger.warning(f"Failed to parse index: {e}")

    return None
