from app.main import app


def test_public_and_internal_route_contract_is_preserved() -> None:
    actual = {
        (method, route.path)
        for route in app.routes
        for method in (route.methods or set())
        if method in {"GET", "POST", "PATCH", "DELETE"}
        and not route.path.startswith(("/docs", "/openapi", "/redoc"))
    }
    expected = {
        ("GET", "/api/health"),
        ("GET", "/health/live"),
        ("GET", "/health/ready"),
        ("GET", "/api/providers"),
        ("GET", "/api/config"),
        ("POST", "/api/client"),
        ("POST", "/api/login"),
        ("GET", "/api/sessions"),
        ("POST", "/api/sessions"),
        ("PATCH", "/api/sessions/{session_id}"),
        ("DELETE", "/api/sessions/{session_id}"),
        ("GET", "/api/sessions/{session_id}/messages"),
        ("POST", "/api/chat"),
        ("GET", "/api/sources/{source_id:path}"),
        ("GET", "/api/sessions/{session_id}/artifacts"),
        ("POST", "/api/sessions/{session_id}/artifacts"),
        ("GET", "/api/ingest/status"),
        ("GET", "/api/ingest/manifest"),
        ("POST", "/api/ingest"),
        ("POST", "/internal/tools/search"),
        ("POST", "/internal/tools/catalog"),
        ("POST", "/internal/tools/resolve-entity"),
        ("GET", "/internal/tools/source/{source_id:path}"),
    }
    assert actual == expected
