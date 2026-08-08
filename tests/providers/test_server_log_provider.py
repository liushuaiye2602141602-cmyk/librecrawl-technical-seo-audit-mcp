"""Server access-log parser and provider tests."""

import json


COMBINED = (
    '66.249.66.1 - - [09/Aug/2026:10:00:00 +0000] '
    '"GET /search?q=private+term HTTP/1.1" 200 1234 "-" '
    '"Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"'
)


def test_combined_parser_classifies_bot_and_redacts_query_values():
    from audit_rules.providers.server_log_provider import parse_log_line
    record = parse_log_line(COMBINED)
    assert record == {
        "method": "GET", "target": "/search?q", "status": 200,
        "bot": "Googlebot", "response_time_ms": None,
    }
    assert "private" not in str(record)
    assert "66.249.66.1" not in str(record)


def test_json_parser_supports_common_nginx_fields_and_duration():
    from audit_rules.providers.server_log_provider import parse_log_line
    line = json.dumps({
        "request_method": "GET", "request_uri": "/product?color=red&size=xl",
        "status": 503, "http_user_agent": "bingbot/2.0", "request_time": 0.245,
        "remote_addr": "203.0.113.9"})
    assert parse_log_line(line) == {
        "method": "GET", "target": "/product?color&size", "status": 503,
        "bot": "Bingbot", "response_time_ms": 245,
    }


def test_malformed_or_human_line_handling():
    from audit_rules.providers.server_log_provider import parse_log_line
    assert parse_log_line("not a log") is None
    human = COMBINED.replace(
        "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
        "Mozilla/5.0 Chrome/120",
    )
    assert parse_log_line(human)["bot"] == "Human/Other"


def test_provider_streams_aggregates_and_marks_truncation(tmp_path, monkeypatch):
    from audit_rules.context import SiteContext
    from audit_rules.providers.server_log_provider import ServerLogDataProvider

    path = tmp_path / "access.log"
    path.write_text("\n".join([COMBINED, "bad", COMBINED, COMBINED]), encoding="utf-8")
    monkeypatch.setenv("MASTER_AUDIT_V3_ENABLED", "true")
    provider = ServerLogDataProvider(path=str(path), max_lines=3)
    shared = {}

    assert provider.is_available()
    assert provider.collect(SiteContext(), [], shared)
    logs = shared["server_logs"]
    assert logs["processed_lines"] == 3
    assert logs["valid_lines"] == 2
    assert logs["malformed_lines"] == 1
    assert logs["bot_counts"] == {"Googlebot": 2}
    assert logs["url_counts"] == {"/search?q": 2}
    assert logs["truncated"] is True


def test_missing_file_and_zero_valid_lines_are_unavailable(tmp_path, monkeypatch):
    from audit_rules.context import SiteContext
    from audit_rules.providers.server_log_provider import ServerLogDataProvider

    monkeypatch.setenv("MASTER_AUDIT_V3_ENABLED", "true")
    assert ServerLogDataProvider(path=str(tmp_path / "missing.log")).is_available() is False

    path = tmp_path / "bad.log"
    path.write_text("bad\nstill bad\n", encoding="utf-8")
    provider = ServerLogDataProvider(path=str(path))
    shared = {}
    assert provider.collect(SiteContext(), [], shared) is False


def test_integration_registers_server_log_provider(monkeypatch):
    from audit_rules import integration
    from audit_rules.providers.server_log_provider import ServerLogDataProvider
    monkeypatch.delenv("SERVER_LOG_PATH", raising=False)
    integration.reset_runner_cache()
    runner = integration._get_runner()
    assert isinstance(runner.providers["Server Logs"], ServerLogDataProvider)
    assert runner.providers["Server Logs"].is_available() is False
