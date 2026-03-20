# tests/scanner/test_sql_scanner.py
from pathlib import Path

from codemap.scanner.sql_scanner import scan_sql


FIXTURE_DIR = Path(__file__).parent.parent / "fixtures"


def test_scan_sql_tables():
    tables = scan_sql([FIXTURE_DIR / "sample.sql"])
    assert len(tables) == 2
    names = {t.name for t in tables}
    assert "users" in names
    assert "departments" in names


def test_scan_sql_columns():
    tables = scan_sql([FIXTURE_DIR / "sample.sql"])
    users = next(t for t in tables if t.name == "users")
    assert len(users.columns) == 4
    id_col = next(c for c in users.columns if c.name == "id")
    assert id_col.pk is True
    email_col = next(c for c in users.columns if c.name == "email")
    assert email_col.nullable is False


def test_scan_sql_foreign_keys():
    tables = scan_sql([FIXTURE_DIR / "sample.sql"])
    users = next(t for t in tables if t.name == "users")
    assert len(users.foreignKeys) == 1
    assert users.foreignKeys[0].column == "dept_id"
    assert users.foreignKeys[0].references == "departments.id"


def test_scan_sql_indexes():
    tables = scan_sql([FIXTURE_DIR / "sample.sql"])
    users = next(t for t in tables if t.name == "users")
    assert len(users.indexes) >= 1
    email_idx = next(i for i in users.indexes if i.name == "idx_users_email")
    assert email_idx.unique is True
    assert "email" in email_idx.columns


def test_scan_sql_invalid_file(tmp_path):
    bad_file = tmp_path / "bad.sql"
    bad_file.write_text("THIS IS NOT SQL AT ALL!!!")
    tables = scan_sql([bad_file])
    assert tables == []  # Graceful skip


def test_scan_sql_empty_list():
    tables = scan_sql([])
    assert tables == []


def test_scan_sql_table_comment():
    tables = scan_sql([FIXTURE_DIR / "sample_with_comments.sql"])
    depts = next(t for t in tables if t.name == "departments")
    assert depts.comment == "부서 관리"
    users = next(t for t in tables if t.name == "users")
    assert users.comment == "사용자 관리"


def test_scan_sql_column_comments():
    tables = scan_sql([FIXTURE_DIR / "sample_with_comments.sql"])
    users = next(t for t in tables if t.name == "users")
    id_col = next(c for c in users.columns if c.name == "id")
    assert id_col.comment == "사용자 고유번호"
    email_col = next(c for c in users.columns if c.name == "email")
    assert email_col.comment == "이메일 주소"
    dept_col = next(c for c in users.columns if c.name == "dept_id")
    assert dept_col.comment == "소속 부서 ID"


def test_scan_sql_no_comment_is_empty():
    tables = scan_sql([FIXTURE_DIR / "sample.sql"])
    users = next(t for t in tables if t.name == "users")
    assert users.comment == ""
    assert all(c.comment == "" for c in users.columns)


def test_scan_sql_comment_escaped_quote(tmp_path):
    sql = tmp_path / "escaped.sql"
    sql.write_text(
        "CREATE TABLE t1 (id INT);\n"
        "COMMENT ON TABLE t1 IS 'it''s a table';\n"
        "COMMENT ON COLUMN t1.id IS 'the ID''s value';\n"
    )
    tables = scan_sql([sql])
    assert tables[0].comment == "it's a table"
    assert tables[0].columns[0].comment == "the ID's value"


def test_scan_sql_comment_schema_qualified(tmp_path):
    sql = tmp_path / "schema.sql"
    sql.write_text(
        "CREATE TABLE t1 (id INT);\n"
        "COMMENT ON TABLE public.t1 IS '스키마 지정 테이블';\n"
        "COMMENT ON COLUMN public.t1.id IS '스키마 지정 컬럼';\n"
    )
    tables = scan_sql([sql])
    assert tables[0].comment == "스키마 지정 테이블"
    assert tables[0].columns[0].comment == "스키마 지정 컬럼"
