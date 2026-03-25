import json
from unittest.mock import patch, MagicMock, call
from codemap.models import (
    ScanResult, DatabaseSchema, Table, Column, ForeignKey,
    ApiSchema, Endpoint, Param, JavaField,
    DependencySchema, ExternalCall, Module,
)
from codemap.ai.client import AiClient
from codemap.ai.enrich_scan import enrich_scan


def _make_client():
    return AiClient("http://localhost:11434", "qwen3:30b", "ko")


def test_enrich_table_comments():
    result = ScanResult(
        project="test",
        database=DatabaseSchema(tables=[
            Table(name="users", columns=[
                Column(name="id", type="BIGINT", pk=True, nullable=False),
                Column(name="email", type="VARCHAR(255)"),
            ]),
        ]),
    )
    client = _make_client()
    ai_response = {
        "table_comment": "사용자 정보를 관리하는 테이블",
        "columns": {
            "id": "사용자 고유 식별자",
            "email": "사용자 이메일 주소",
        },
    }
    with patch.object(client, "chat_json", return_value=ai_response):
        enrich_scan(result, client)

    assert result.database.tables[0].comment == "사용자 정보를 관리하는 테이블"
    assert result.database.tables[0].columns[0].comment == "사용자 고유 식별자"
    assert result.database.tables[0].columns[1].comment == "사용자 이메일 주소"


def test_enrich_skips_existing_comments():
    result = ScanResult(
        project="test",
        database=DatabaseSchema(tables=[
            Table(name="users", comment="기존 설명", columns=[
                Column(name="id", type="BIGINT", comment="기존 컬럼 설명"),
            ]),
        ]),
    )
    client = _make_client()
    with patch.object(client, "chat_json") as mock_chat:
        enrich_scan(result, client)
    mock_chat.assert_not_called()


def test_enrich_endpoint_descriptions():
    result = ScanResult(
        project="test",
        api=ApiSchema(endpoints=[
            Endpoint(
                method="GET", path="/api/users",
                controller="UserController", service="UserService",
            ),
        ]),
    )
    client = _make_client()
    ai_response = {
        "endpoints": [
            {"method": "GET", "path": "/api/users", "description": "사용자 목록 조회"},
        ],
    }
    with patch.object(client, "chat_json", return_value=ai_response):
        enrich_scan(result, client)

    assert result.api.endpoints[0].description == "사용자 목록 조회"


def test_enrich_external_call_descriptions():
    result = ScanResult(
        project="test",
        dependencies=DependencySchema(externalCalls=[
            ExternalCall(
                source="GdalService", type="gdal",
                command="gdal_translate", file="GdalService.java", line=10,
            ),
        ]),
    )
    client = _make_client()
    ai_response = {
        "calls": [
            {"index": 0, "description": "래스터 이미지 형식을 변환한다"},
        ],
    }
    with patch.object(client, "chat_json", return_value=ai_response):
        enrich_scan(result, client)

    assert result.dependencies.externalCalls[0].description == "래스터 이미지 형식을 변환한다"


def test_enrich_scan_with_disabled_client():
    result = ScanResult(
        project="test",
        database=DatabaseSchema(tables=[
            Table(name="users", columns=[
                Column(name="id", type="BIGINT"),
            ]),
        ]),
    )
    client = _make_client()
    client._disabled = True
    with patch.object(client, "chat_json") as mock_chat:
        enrich_scan(result, client)
    mock_chat.assert_not_called()


def test_enrich_scan_ai_returns_none():
    result = ScanResult(
        project="test",
        database=DatabaseSchema(tables=[
            Table(name="users", columns=[
                Column(name="id", type="BIGINT"),
            ]),
        ]),
    )
    client = _make_client()
    with patch.object(client, "chat_json", return_value=None):
        enrich_scan(result, client)

    assert result.database.tables[0].comment == ""
    assert result.database.tables[0].columns[0].comment == ""
