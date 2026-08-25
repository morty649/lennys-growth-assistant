from app.security import failure_code, redact_text


def test_redacts_headers_keys_and_database_passwords() -> None:
    value = (
        "Authorization: Bearer gsk_super_secret_value_12345 "
        "api_key=sk-ant-super-secret-value postgresql://user:password@localhost/db"
    )
    redacted = redact_text(value)

    assert "super_secret" not in redacted
    assert "super-secret" not in redacted
    assert ":password@" not in redacted
    assert redacted.count("[REDACTED]") >= 3


def test_failure_codes_do_not_include_upstream_content() -> None:
    assert failure_code(TimeoutError("secret upstream body")) == "provider_timeout"
    assert failure_code(RuntimeError("API_KEY not configured")) == "provider_not_configured"
