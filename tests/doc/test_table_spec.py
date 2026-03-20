from codemap.models import DatabaseSchema, Table, Column, ForeignKey, Index
from codemap.doc.table_spec import generate_table_spec


def _sample_db():
    return DatabaseSchema(tables=[
        Table(name="users", columns=[
            Column(name="id", type="BIGINT", pk=True, nullable=False),
            Column(name="email", type="VARCHAR(255)", nullable=False),
            Column(name="dept_id", type="BIGINT"),
        ], foreignKeys=[ForeignKey(column="dept_id", references="departments.id")],
        indexes=[Index(name="idx_users_email", columns=["email"], unique=True)]),
    ])


def test_table_spec_header():
    md = generate_table_spec(_sample_db())
    assert "# 테이블 정의서" in md


def test_table_spec_table_section():
    md = generate_table_spec(_sample_db())
    assert "## users" in md
    assert "| 컬럼명 |" in md
    assert "| id " in md


def test_table_spec_pk_marker():
    md = generate_table_spec(_sample_db())
    assert "O" in md


def test_table_spec_fk():
    md = generate_table_spec(_sample_db())
    assert "departments.id" in md


def test_table_spec_index():
    md = generate_table_spec(_sample_db())
    assert "idx_users_email" in md
    assert "UNIQUE" in md


def test_table_spec_empty():
    md = generate_table_spec(DatabaseSchema())
    assert "# 테이블 정의서" in md
