from codemap.models import ApiSchema, Endpoint, Param, JavaField
from codemap.doc.api_spec import generate_api_spec


def test_api_spec_header():
    md = generate_api_spec(ApiSchema(endpoints=[
        Endpoint(method="GET", path="/api/users", controller="UserController",
                 service="UserService", calls=["UserRepository.findAll"]),
    ]))
    assert "# API 명세서" in md
    assert "GET" in md
    assert "/api/users" in md
    assert "UserController" in md


def test_api_spec_empty():
    md = generate_api_spec(ApiSchema())
    assert "# API 명세서" in md


def test_api_spec_params_and_return():
    api = ApiSchema(endpoints=[
        Endpoint(
            method="GET", path="/api/devices",
            controller="DeviceApiController", service="DeviceService",
            params=[Param(name="deviceType", type="String", annotation="RequestParam", required=False)],
            returnType="ApiResponse<List<Device>>",
        ),
    ])
    md = generate_api_spec(api)
    assert "deviceType" in md
    assert "RequestParam" in md
    assert "ApiResponse" in md or "List<Device>" in md


def test_api_spec_detailed_endpoint():
    """엔드포인트별 섹션에 입력/응답 필드 테이블이 출력됨"""
    api = ApiSchema(endpoints=[
        Endpoint(
            method="GET", path="/api/devices",
            controller="DeviceApiController", service="DeviceService",
            params=[Param(name="deviceType", type="String", annotation="RequestParam", required=False)],
            returnType="ApiResponse<List<Device>>",
            responseFields=[
                JavaField(name="deviceId", type="Integer", comment="고유번호"),
                JavaField(name="deviceName", type="String", comment="장비명"),
                JavaField(name="status", type="String", comment="상태"),
            ],
        ),
    ])
    md = generate_api_spec(api)
    assert "## GET /api/devices" in md
    assert "deviceType" in md
    assert "RequestParam" in md
    assert "deviceId" in md
    assert "고유번호" in md
    assert "장비명" in md


def test_api_spec_detailed_request_body():
    """@RequestBody 엔드포인트에 requestFields 테이블이 출력됨"""
    api = ApiSchema(endpoints=[
        Endpoint(
            method="POST", path="/api/users",
            controller="UserController", service="UserService",
            params=[Param(name="user", type="User", annotation="RequestBody")],
            returnType="ApiResponse<User>",
            requestFields=[
                JavaField(name="email", type="String", comment="이메일 주소"),
                JavaField(name="name", type="String", comment="사용자명"),
            ],
            responseFields=[
                JavaField(name="id", type="Long", comment="고유번호"),
                JavaField(name="email", type="String", comment="이메일 주소"),
            ],
        ),
    ])
    md = generate_api_spec(api)
    assert "## POST /api/users" in md
    assert "### 요청 본문" in md
    assert "이메일 주소" in md
    assert "### 응답" in md
    assert "고유번호" in md


def test_api_spec_detailed_no_fields():
    """필드 정보가 없는 엔드포인트는 기본 정보만 표시"""
    api = ApiSchema(endpoints=[
        Endpoint(
            method="GET", path="/api/health",
            controller="HealthController", service="",
            returnType="String",
        ),
    ])
    md = generate_api_spec(api)
    assert "## GET /api/health" in md


def test_api_spec_summary_table():
    """상단에 요약 테이블이 포함됨"""
    api = ApiSchema(endpoints=[
        Endpoint(method="GET", path="/api/test", controller="C", service="S"),
    ])
    md = generate_api_spec(api)
    assert "# API 명세서" in md
    assert "| 메서드 |" in md or "메서드" in md
