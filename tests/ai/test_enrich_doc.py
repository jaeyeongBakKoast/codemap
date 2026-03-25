from unittest.mock import patch
from codemap.models import (
    ScanResult, DatabaseSchema, Table, Column, ForeignKey,
    ApiSchema, Endpoint, DependencySchema,
)
from codemap.ai.client import AiClient
from codemap.ai.enrich_doc import (
    generate_table_relationships,
    generate_business_logic,
    generate_overview_narrative,
)


def _make_client():
    return AiClient("http://localhost:11434", "qwen3:30b", "ko")


def test_generate_table_relationships():
    db = DatabaseSchema(tables=[
        Table(name="users", columns=[
            Column(name="id", type="BIGINT", pk=True),
        ]),
        Table(name="orders", columns=[
            Column(name="id", type="BIGINT", pk=True),
            Column(name="user_id", type="BIGINT"),
        ], foreignKeys=[ForeignKey(column="user_id", references="users.id")]),
    ])
    client = _make_client()
    ai_text = "- `orders` 테이블은 `users` 테이블과 다대일 관계이다."
    with patch.object(client, "chat", return_value=ai_text):
        result = generate_table_relationships(db, client)
    assert "orders" in result
    assert "users" in result


def test_generate_table_relationships_no_fks():
    db = DatabaseSchema(tables=[
        Table(name="logs", columns=[Column(name="id", type="BIGINT")]),
    ])
    client = _make_client()
    result = generate_table_relationships(db, client)
    assert result == ""


def test_generate_business_logic():
    ep = Endpoint(
        method="POST", path="/api/users",
        controller="UserController", service="UserService",
        calls=["UserRepository.save", "EmailService.sendWelcome"],
    )
    client = _make_client()
    ai_text = "사용자 정보를 저장하고 환영 이메일을 발송한다."
    with patch.object(client, "chat", return_value=ai_text):
        result = generate_business_logic(ep, client)
    assert "사용자" in result


def test_generate_overview_narrative():
    scan = ScanResult(
        project="my-project",
        database=DatabaseSchema(tables=[
            Table(name="users", columns=[]),
            Table(name="orders", columns=[]),
        ]),
        api=ApiSchema(endpoints=[
            Endpoint(method="GET", path="/api/users",
                     controller="UserController", service="UserService"),
        ]),
    )
    client = _make_client()
    ai_text = "my-project는 사용자와 주문을 관리하는 웹 애플리케이션이다."
    with patch.object(client, "chat", return_value=ai_text):
        result = generate_overview_narrative(scan, client)
    assert "my-project" in result


def test_generate_overview_narrative_disabled_client():
    scan = ScanResult(project="test")
    client = _make_client()
    client._disabled = True
    result = generate_overview_narrative(scan, client)
    assert result == ""
