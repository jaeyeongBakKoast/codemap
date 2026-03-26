from pathlib import Path

from codemap.scanner.java_scanner import scan_java
from codemap.models import Endpoint, Module

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures"


def test_scan_java_endpoints():
    endpoints, modules, _ = scan_java(
        [FIXTURE_DIR / "UserController.java", FIXTURE_DIR / "UserService.java"]
    )
    assert len(endpoints) >= 3
    paths = {ep.path for ep in endpoints}
    assert any("/api/users" in p for p in paths)


def test_scan_java_endpoint_details():
    endpoints, _, _ = scan_java(
        [FIXTURE_DIR / "UserController.java", FIXTURE_DIR / "UserService.java"]
    )
    get_all = next((ep for ep in endpoints if ep.method == "GET" and ep.path == "/api/users"), None)
    assert get_all is not None
    assert get_all.controller == "UserController"
    assert get_all.service == "UserService"


def test_scan_java_modules():
    _, modules, _ = scan_java(
        [FIXTURE_DIR / "UserController.java", FIXTURE_DIR / "UserService.java"]
    )
    service_mod = next((m for m in modules if m.name == "UserService"), None)
    assert service_mod is not None
    assert "UserRepository" in service_mod.dependsOn
    assert "EmailService" in service_mod.dependsOn
    assert service_mod.layer == "service"


def test_scan_java_controller_module():
    _, modules, _ = scan_java(
        [FIXTURE_DIR / "UserController.java", FIXTURE_DIR / "UserService.java"]
    )
    ctrl_mod = next((m for m in modules if m.name == "UserController"), None)
    assert ctrl_mod is not None
    assert ctrl_mod.layer == "controller"
    assert "UserService" in ctrl_mod.dependsOn


def test_scan_java_empty():
    endpoints, modules, class_fields = scan_java([])
    assert endpoints == []
    assert modules == []
    assert class_fields == {}


def test_scan_java_endpoint_params():
    endpoints, _, _ = scan_java(
        [FIXTURE_DIR / "UserController.java", FIXTURE_DIR / "UserService.java"]
    )
    get_all = next((ep for ep in endpoints if ep.method == "GET" and ep.path == "/api/users"), None)
    assert get_all is not None
    assert len(get_all.params) == 1
    assert get_all.params[0].name == "status"
    assert get_all.params[0].annotation == "RequestParam"
    assert get_all.params[0].required is False


def test_scan_java_endpoint_request_body():
    endpoints, _, _ = scan_java(
        [FIXTURE_DIR / "UserController.java", FIXTURE_DIR / "UserService.java"]
    )
    post = next((ep for ep in endpoints if ep.method == "POST"), None)
    assert post is not None
    assert len(post.params) == 1
    assert post.params[0].annotation == "RequestBody"
    assert post.params[0].type == "User"


def test_scan_java_endpoint_path_variable():
    endpoints, _, _ = scan_java(
        [FIXTURE_DIR / "UserController.java", FIXTURE_DIR / "UserService.java"]
    )
    get_by_id = next((ep for ep in endpoints if "/{id}" in ep.path or ep.path.endswith("/{id}")), None)
    assert get_by_id is not None
    assert any(p.annotation == "PathVariable" for p in get_by_id.params)


def test_scan_java_return_type():
    endpoints, _, _ = scan_java(
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
    endpoints, _, _ = scan_java([java_file])
    assert len(endpoints) == 1
    assert len(endpoints[0].params) == 2
    assert endpoints[0].params[0].name == "keyword"
    assert endpoints[0].params[0].required is True
    assert endpoints[0].params[1].name == "page"
    assert endpoints[0].params[1].required is False


def test_scan_java_class_fields():
    """Entity/DTO 클래스의 필드와 주석을 파싱"""
    endpoints, modules, class_fields = scan_java(
        [FIXTURE_DIR / "User.java"]
    )
    assert "User" in class_fields
    fields = class_fields["User"]
    assert len(fields) == 5
    id_field = next(f for f in fields if f.name == "id")
    assert id_field.type == "Long"
    assert id_field.comment == "사용자 고유번호"
    email_field = next(f for f in fields if f.name == "email")
    assert email_field.comment == "이메일 주소"


def test_scan_java_class_fields_with_final(tmp_path):
    """private final 필드에서 final을 제거하고 타입만 추출"""
    java_file = tmp_path / "FinalFields.java"
    java_file.write_text(
        "public class FinalFields {\n"
        "    // 서비스\n"
        "    private final UserService userService;\n"
        "    // 이름\n"
        "    private String name;\n"
        "}\n"
    )
    _, _, class_fields = scan_java([java_file])
    assert "FinalFields" in class_fields
    fields = class_fields["FinalFields"]
    svc = next(f for f in fields if f.name == "userService")
    assert svc.type == "UserService"
    assert svc.comment == "서비스"


def test_scan_java_request_fields_resolved():
    """@RequestBody 타입의 필드가 requestFields로 해석됨"""
    endpoints, modules, class_fields = scan_java([
        FIXTURE_DIR / "UserController.java",
        FIXTURE_DIR / "UserService.java",
        FIXTURE_DIR / "User.java",
    ])
    post = next((ep for ep in endpoints if ep.method == "POST"), None)
    assert post is not None
    assert len(post.requestFields) > 0
    assert any(f.name == "email" for f in post.requestFields)


def test_scan_java_response_fields_resolved():
    """반환 타입에서 inner type을 해석하여 responseFields로 채움"""
    endpoints, modules, class_fields = scan_java([
        FIXTURE_DIR / "UserController.java",
        FIXTURE_DIR / "UserService.java",
        FIXTURE_DIR / "User.java",
    ])
    get_all = next((ep for ep in endpoints if ep.method == "GET" and ep.path == "/api/users"), None)
    assert get_all is not None
    assert len(get_all.responseFields) > 0
    assert any(f.name == "id" for f in get_all.responseFields)


def test_scan_java_response_fields_unresolved():
    """알 수 없는 타입이면 responseFields는 빈 리스트"""
    endpoints, modules, class_fields = scan_java([
        FIXTURE_DIR / "UserController.java",
        FIXTURE_DIR / "UserService.java",
    ])
    get_all = next((ep for ep in endpoints if ep.method == "GET" and ep.path == "/api/users"), None)
    assert get_all is not None
    assert get_all.responseFields == []


def test_scan_java_generic_wrapper_response_fields():
    """ResultResponse<CampaignResponse> → 트리 구조: wrapper 필드 + payload.children에 inner type"""
    endpoints, _, class_fields = scan_java([
        FIXTURE_DIR / "CampaignController.java",
        FIXTURE_DIR / "ResultResponse.java",
        FIXTURE_DIR / "CampaignResponse.java",
    ])
    assert "ResultResponse" in class_fields
    assert "CampaignResponse" in class_fields

    # GET /api/campaigns/{id} → ResultResponse<CampaignResponse>
    get_one = next((ep for ep in endpoints if ep.path == "/api/campaigns/{id}"), None)
    assert get_one is not None
    field_names = [f.name for f in get_one.responseFields]
    # ResultResponse 필드가 최상위에 있어야 함
    assert "status" in field_names
    assert "message" in field_names
    assert "payload" in field_names
    # payload 필드의 children에 CampaignResponse 필드가 있어야 함
    payload = next(f for f in get_one.responseFields if f.name == "payload")
    assert payload.type == "CampaignResponse"
    child_names = [c.name for c in payload.children]
    assert "campaignId" in child_names
    assert "campaignName" in child_names


def test_scan_java_generic_wrapper_list_response_fields():
    """ResultResponse<List<CampaignResponse>> → payload.type이 List<CampaignResponse>"""
    endpoints, _, class_fields = scan_java([
        FIXTURE_DIR / "CampaignController.java",
        FIXTURE_DIR / "ResultResponse.java",
        FIXTURE_DIR / "CampaignResponse.java",
    ])
    get_all = next((ep for ep in endpoints if ep.path == "/api/campaigns"), None)
    assert get_all is not None
    field_names = [f.name for f in get_all.responseFields]
    assert "status" in field_names
    assert "payload" in field_names
    payload = next(f for f in get_all.responseFields if f.name == "payload")
    assert payload.type == "List<CampaignResponse>"
    child_names = [c.name for c in payload.children]
    assert "campaignId" in child_names
