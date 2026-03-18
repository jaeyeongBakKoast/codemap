from datetime import datetime

from codemap.models import (
    ScanResult,
    Table,
    Column,
    ForeignKey,
    Index,
    Endpoint,
    Module,
    ExternalCall,
    Component,
    ApiCall,
)


def test_scan_result_empty():
    result = ScanResult(project="test")
    assert result.version == "1.0"
    assert result.project == "test"
    assert result.database.tables == []
    assert result.api.endpoints == []
    assert result.dependencies.modules == []
    assert result.frontend.components == []


def test_table_with_columns():
    col = Column(name="id", type="BIGINT", pk=True, nullable=False)
    fk = ForeignKey(column="dept_id", references="departments.id")
    idx = Index(name="idx_email", columns=["email"], unique=True)
    table = Table(name="users", columns=[col], foreignKeys=[fk], indexes=[idx])
    assert table.name == "users"
    assert table.columns[0].pk is True
    assert table.foreignKeys[0].references == "departments.id"


def test_endpoint():
    ep = Endpoint(
        method="POST",
        path="/api/users",
        controller="UserController",
        service="UserService",
        calls=["UserRepository.save"],
    )
    assert ep.method == "POST"
    assert ep.controller == "UserController"


def test_module():
    mod = Module(
        name="UserService",
        type="service",
        file="src/main/java/UserService.java",
        dependsOn=["UserRepository"],
        layer="service",
    )
    assert mod.layer == "service"


def test_external_call():
    ec = ExternalCall(
        source="GdalService.convert",
        type="process",
        command="gdal_translate",
        file="GdalService.java",
        line=42,
    )
    assert ec.type == "process"


def test_component():
    comp = Component(
        name="UserList",
        file="UserList.tsx",
        children=["UserCard"],
        hooks=["useState"],
    )
    assert comp.children == ["UserCard"]


def test_api_call():
    ac = ApiCall(
        component="UserList",
        method="GET",
        path="/api/users",
        file="UserList.tsx",
        line=15,
    )
    assert ac.method == "GET"


def test_scan_result_to_json():
    result = ScanResult(project="test")
    data = result.model_dump()
    assert data["version"] == "1.0"
    assert "database" in data
    assert "api" in data
    assert isinstance(data["scannedAt"], datetime)


def test_external_call_via_alias():
    ec = ExternalCall(**{"from": "GdalService.convert", "type": "process", "command": "gdal_translate", "file": "GdalService.java", "line": 42})
    assert ec.source == "GdalService.convert"
    assert ec.type == "process"


def test_external_call_serialization():
    ec = ExternalCall(source="GdalService.convert", type="process", command="gdal_translate", file="GdalService.java", line=42)
    dumped = ec.model_dump(by_alias=True)
    assert "from" in dumped
    assert dumped["from"] == "GdalService.convert"
    assert "source" not in dumped
