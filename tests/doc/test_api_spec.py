from codemap.models import ApiSchema, Endpoint
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
