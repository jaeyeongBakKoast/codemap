from codemap.models import (
    ScanResult, DatabaseSchema, Table, Column, ForeignKey,
    ApiSchema, Endpoint, DependencySchema, Module, ExternalCall,
)
from codemap.renderer.mermaid import render_erd, render_sequence, render_architecture, render_component


def _sample_db():
    return DatabaseSchema(tables=[
        Table(name="users", columns=[
            Column(name="id", type="BIGINT", pk=True, nullable=False),
            Column(name="email", type="VARCHAR(255)", nullable=False),
            Column(name="dept_id", type="BIGINT"),
        ], foreignKeys=[ForeignKey(column="dept_id", references="departments.id")]),
        Table(name="departments", columns=[
            Column(name="id", type="BIGINT", pk=True, nullable=False),
            Column(name="name", type="VARCHAR(255)", nullable=False),
        ]),
    ])


def test_render_erd_mermaid():
    result = render_erd(_sample_db())
    assert "erDiagram" in result
    assert "USERS" in result
    assert "DEPARTMENTS" in result
    assert "BIGINT id PK" in result


def test_render_erd_relationships():
    result = render_erd(_sample_db())
    assert "USERS" in result and "DEPARTMENTS" in result
    assert "}o--||" in result or "||--o{" in result or "--" in result


def test_render_sequence():
    endpoints = [
        Endpoint(method="POST", path="/api/users", controller="UserController",
                 service="UserService", calls=["UserRepository.save", "EmailService.send"]),
    ]
    result = render_sequence(
        ApiSchema(endpoints=endpoints),
        DependencySchema(),
        entries=["UserController", "UserService", "UserRepository.save", "EmailService.send"],
        label="사용자 생성",
    )
    assert "sequenceDiagram" in result
    assert "사용자 생성" in result


def test_render_architecture():
    scan = ScanResult(project="test")
    scan.database = _sample_db()
    scan.api = ApiSchema(endpoints=[
        Endpoint(method="GET", path="/api/users", controller="UserController",
                 service="UserService", calls=["UserRepository.findAll"]),
    ])
    scan.dependencies = DependencySchema(modules=[
        Module(name="UserService", type="service", file="UserService.java",
               dependsOn=["UserRepository"], layer="service"),
    ], externalCalls=[
        ExternalCall(source="GdalService.convert", type="process",
                     command="gdal_translate", file="GdalService.java", line=42),
    ])
    result = render_architecture(scan)
    assert "graph" in result or "flowchart" in result
    assert "Frontend" in result or "Backend" in result or "Database" in result


def test_render_component():
    deps = DependencySchema(modules=[
        Module(name="UserService", type="service", file="a.java",
               dependsOn=["UserRepository", "EmailService"], layer="service"),
        Module(name="UserRepository", type="repository", file="b.java",
               dependsOn=[], layer="repository"),
    ])
    result = render_component(deps)
    assert "graph" in result or "flowchart" in result
    assert "UserService" in result
    assert "UserRepository" in result


def test_render_erd_empty():
    result = render_erd(DatabaseSchema())
    assert "erDiagram" in result
