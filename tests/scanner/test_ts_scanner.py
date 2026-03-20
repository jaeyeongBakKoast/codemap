from pathlib import Path

from codemap.scanner.ts_scanner import scan_typescript
from codemap.models import Component, ApiCall

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures"


def test_scan_ts_components():
    components, api_calls = scan_typescript([FIXTURE_DIR / "UserList.tsx"])
    assert len(components) >= 1
    user_list = next((c for c in components if c.name == "UserList"), None)
    assert user_list is not None
    assert "UserCard" in user_list.children
    assert "Pagination" in user_list.children


def test_scan_ts_hooks():
    components, _ = scan_typescript([FIXTURE_DIR / "UserList.tsx"])
    user_list = next(c for c in components if c.name == "UserList")
    assert "useState" in user_list.hooks
    assert "useEffect" in user_list.hooks


def test_scan_ts_api_calls():
    _, api_calls = scan_typescript([FIXTURE_DIR / "UserList.tsx"])
    assert len(api_calls) >= 1
    get_call = next((a for a in api_calls if a.method == "GET"), None)
    assert get_call is not None
    assert get_call.path == "/api/users"
    assert get_call.component == "UserList"


def test_scan_ts_empty():
    components, api_calls = scan_typescript([])
    assert components == []
    assert api_calls == []
