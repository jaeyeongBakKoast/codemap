from codemap.models import ScanResult, DatabaseSchema, Table, Column, ApiSchema, Endpoint, DependencySchema, ExternalCall
from codemap.doc.overview import generate_overview


def test_overview_contains_sections():
    scan = ScanResult(project="my-project")
    scan.database = DatabaseSchema(tables=[
        Table(name="users", columns=[Column(name="id", type="BIGINT", pk=True)]),
    ])
    scan.api = ApiSchema(endpoints=[
        Endpoint(method="GET", path="/api/users", controller="UserController",
                 service="UserService", calls=[]),
    ])
    scan.dependencies = DependencySchema(externalCalls=[
        ExternalCall(source="GdalService.convert", type="process",
                     command="gdal_translate", file="GdalService.java", line=42),
    ])
    md = generate_overview(scan)
    assert "# 프로젝트 개요" in md
    assert "my-project" in md


def test_overview_empty():
    md = generate_overview(ScanResult(project="empty"))
    assert "# 프로젝트 개요" in md
