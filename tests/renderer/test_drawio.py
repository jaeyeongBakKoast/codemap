import xml.etree.ElementTree as ET

from codemap.models import (
    DatabaseSchema, Table, Column, ForeignKey, DependencySchema, Module,
    ScanResult, ApiSchema, Endpoint, ExternalCall,
)
from codemap.renderer.drawio import (
    render_erd_drawio, render_sequence_drawio,
    render_architecture_drawio, render_component_drawio,
)


def _sample_db():
    return DatabaseSchema(tables=[
        Table(name="users", columns=[
            Column(name="id", type="BIGINT", pk=True, nullable=False),
            Column(name="email", type="VARCHAR(255)"),
        ], foreignKeys=[ForeignKey(column="dept_id", references="departments.id")]),
        Table(name="departments", columns=[
            Column(name="id", type="BIGINT", pk=True, nullable=False),
            Column(name="name", type="VARCHAR(255)"),
        ]),
    ])


def test_drawio_erd_valid_xml():
    result = render_erd_drawio(_sample_db())
    root = ET.fromstring(result)
    assert root.tag == "mxfile"


def test_drawio_erd_contains_tables():
    result = render_erd_drawio(_sample_db())
    assert "users" in result
    assert "departments" in result


def test_drawio_sequence_valid_xml():
    api = ApiSchema(endpoints=[
        Endpoint(method="POST", path="/api/users", controller="UserController",
                 service="UserService", calls=["UserRepository.save"]),
    ])
    result = render_sequence_drawio(
        api, DependencySchema(),
        entries=["UserController", "UserService", "UserRepository.save"],
        label="사용자 생성",
    )
    root = ET.fromstring(result)
    assert root.tag == "mxfile"
    assert "UserController" in result


def test_drawio_architecture_valid_xml():
    scan = ScanResult(project="test")
    scan.database = _sample_db()
    scan.api = ApiSchema(endpoints=[
        Endpoint(method="GET", path="/api/users", controller="UserController",
                 service="UserService", calls=["UserRepository.findAll"]),
    ])
    result = render_architecture_drawio(scan)
    root = ET.fromstring(result)
    assert root.tag == "mxfile"


def test_drawio_component_valid_xml():
    deps = DependencySchema(modules=[
        Module(name="UserService", type="service", file="a.java",
               dependsOn=["UserRepository"], layer="service"),
    ])
    result = render_component_drawio(deps)
    root = ET.fromstring(result)
    assert root.tag == "mxfile"
    assert "UserService" in result
