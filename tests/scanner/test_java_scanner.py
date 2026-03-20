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


def test_scan_java_endpoint_params():
    endpoints, _ = scan_java(
        [FIXTURE_DIR / "UserController.java", FIXTURE_DIR / "UserService.java"]
    )
    get_all = next((ep for ep in endpoints if ep.method == "GET" and ep.path == "/api/users"), None)
    assert get_all is not None
    assert len(get_all.params) == 1
    assert get_all.params[0].name == "status"
    assert get_all.params[0].annotation == "RequestParam"
    assert get_all.params[0].required is False


def test_scan_java_endpoint_request_body():
    endpoints, _ = scan_java(
        [FIXTURE_DIR / "UserController.java", FIXTURE_DIR / "UserService.java"]
    )
    post = next((ep for ep in endpoints if ep.method == "POST"), None)
    assert post is not None
    assert len(post.params) == 1
    assert post.params[0].annotation == "RequestBody"
    assert post.params[0].type == "User"


def test_scan_java_endpoint_path_variable():
    endpoints, _ = scan_java(
        [FIXTURE_DIR / "UserController.java", FIXTURE_DIR / "UserService.java"]
    )
    get_by_id = next((ep for ep in endpoints if "/{id}" in ep.path or ep.path.endswith("/{id}")), None)
    assert get_by_id is not None
    assert any(p.annotation == "PathVariable" for p in get_by_id.params)


def test_scan_java_return_type():
    endpoints, _ = scan_java(
        [FIXTURE_DIR / "UserController.java", FIXTURE_DIR / "UserService.java"]
    )
    get_all = next((ep for ep in endpoints if ep.method == "GET" and ep.path == "/api/users"), None)
    assert get_all is not None
    assert "List<User>" in get_all.returnType or "ApiResponse" in get_all.returnType


def test_scan_java_multi_params(tmp_path):
    java_file = tmp_path / "MultiController.java"
    java_file.write_text(
        '@RestController\n@RequestMapping("/api/search")\n'
        'public class MultiController {\n'
        '    @GetMapping\n'
        '    public ApiResponse<List<Item>> search(\n'
        '            @RequestParam String keyword,\n'
        '            @RequestParam(required = false) Integer page) {\n'
        '        return null;\n'
        '    }\n'
        '}\n'
    )
    endpoints, _ = scan_java([java_file])
    assert len(endpoints) == 1
    assert len(endpoints[0].params) == 2
    assert endpoints[0].params[0].name == "keyword"
    assert endpoints[0].params[0].required is True
    assert endpoints[0].params[1].name == "page"
    assert endpoints[0].params[1].required is False
