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
