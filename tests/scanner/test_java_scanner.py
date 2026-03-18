from pathlib import Path

from codemap.scanner.java_scanner import scan_java
from codemap.models import Endpoint, Module

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures"


def test_scan_java_endpoints():
    endpoints, modules = scan_java(
        [FIXTURE_DIR / "UserController.java", FIXTURE_DIR / "UserService.java"]
    )
    assert len(endpoints) >= 3
    paths = {ep.path for ep in endpoints}
    assert any("/api/users" in p for p in paths)


def test_scan_java_endpoint_details():
    endpoints, _ = scan_java(
        [FIXTURE_DIR / "UserController.java", FIXTURE_DIR / "UserService.java"]
    )
    get_all = next((ep for ep in endpoints if ep.method == "GET" and ep.path == "/api/users"), None)
    assert get_all is not None
    assert get_all.controller == "UserController"
    assert get_all.service == "UserService"


def test_scan_java_modules():
    _, modules = scan_java(
        [FIXTURE_DIR / "UserController.java", FIXTURE_DIR / "UserService.java"]
    )
    service_mod = next((m for m in modules if m.name == "UserService"), None)
    assert service_mod is not None
    assert "UserRepository" in service_mod.dependsOn
    assert "EmailService" in service_mod.dependsOn
    assert service_mod.layer == "service"


def test_scan_java_controller_module():
    _, modules = scan_java(
        [FIXTURE_DIR / "UserController.java", FIXTURE_DIR / "UserService.java"]
    )
    ctrl_mod = next((m for m in modules if m.name == "UserController"), None)
    assert ctrl_mod is not None
    assert ctrl_mod.layer == "controller"
    assert "UserService" in ctrl_mod.dependsOn


def test_scan_java_empty():
    endpoints, modules = scan_java([])
    assert endpoints == []
    assert modules == []
