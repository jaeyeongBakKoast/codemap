from codemap.models import ApiSchema, Endpoint, Param
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
