from datetime import datetime

from codemap.models import (
    ScanResult,
    Table,
    Column,
    ForeignKey,
    Index,
    Endpoint,
    Param,
    JavaField,
    Module,
    ExternalCall,
    Component,
    ApiCall,
    ApiSchema,
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


def test_column_comment():
    col = Column(name="id", type="BIGINT", pk=True, nullable=False, comment="고유번호")
    assert col.comment == "고유번호"


def test_column_comment_default():
    col = Column(name="id", type="BIGINT")
    assert col.comment == ""


def test_table_comment():
    table = Table(name="users", comment="사용자 관리")
    assert table.comment == "사용자 관리"


def test_endpoint_params():
    ep = Endpoint(
        method="GET",
        path="/api/devices",
        controller="DeviceApiController",
        service="DeviceService",
        params=[
            Param(name="deviceType", type="String", annotation="RequestParam", required=False),
        ],
        returnType="ApiResponse<List<Device>>",
    )
    assert len(ep.params) == 1
    assert ep.params[0].annotation == "RequestParam"
    assert ep.returnType == "ApiResponse<List<Device>>"


def test_endpoint_params_default():
    ep = Endpoint(method="GET", path="/api/test", controller="C", service="S")
    assert ep.params == []
    assert ep.returnType == ""


def test_java_field():
    field = JavaField(name="deviceId", type="Integer", comment="고유번호")
    assert field.name == "deviceId"
    assert field.type == "Integer"
    assert field.comment == "고유번호"


def test_java_field_default_comment():
    field = JavaField(name="id", type="Long")
    assert field.comment == ""


def test_endpoint_request_fields():
    ep = Endpoint(
        method="POST", path="/api/users", controller="C", service="S",
        requestFields=[
            JavaField(name="email", type="String", comment="이메일"),
        ],
    )
    assert len(ep.requestFields) == 1
    assert ep.requestFields[0].comment == "이메일"


def test_endpoint_response_fields():
    ep = Endpoint(
        method="GET", path="/api/users", controller="C", service="S",
        responseFields=[
            JavaField(name="deviceId", type="Integer", comment="고유번호"),
            JavaField(name="deviceName", type="String", comment="장비명"),
        ],
    )
    assert len(ep.responseFields) == 2


def test_endpoint_fields_default():
    ep = Endpoint(method="GET", path="/api/test", controller="C", service="S")
    assert ep.requestFields == []
    assert ep.responseFields == []


def test_api_schema_class_fields():
    schema = ApiSchema(
        classFields={"User": [JavaField(name="id", type="Long", comment="고유번호")]},
    )
    assert "User" in schema.classFields
    assert schema.classFields["User"][0].name == "id"


def test_api_schema_class_fields_default():
    schema = ApiSchema()
    assert schema.classFields == {}
