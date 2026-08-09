"""Validated environment defaults for production audit operations."""


def test_operational_config_parses_bounded_runtime_controls():
    from audit_rules.configuration import load_operational_settings

    settings, errors = load_operational_settings({
        "AUDIT_FETCH_TIMEOUT_SECONDS": "45",
        "AUDIT_FETCH_WORKERS": "6",
        "AUDIT_EXTERNAL_FETCH_WORKERS": "12",
        "AUDIT_FETCH_DELAY_MS": "750",
        "AUDIT_CONTENT_SAMPLE_LIMIT": "900",
        "AUDIT_EXTENDED_SAMPLE_LIMIT": "800",
        "AUDIT_REPORT_PDF_ENABLED": "false",
        "AUDIT_MASTER_REPORT_ENABLED": "true",
        "AUDIT_FILL_SITEMAP_ORPHANS": "false",
    })

    assert errors == []
    assert settings == {
        "fetch_timeout_s": 45.0, "fetch_workers": 6,
        "external_fetch_workers": 12, "fetch_delay_ms": 750.0,
        "content_check_limit": 900, "extended_check_limit": 800,
        "report_pdf_enabled": False, "master_report_enabled": True,
        "fill_sitemap_orphans": False,
    }


def test_invalid_operational_config_falls_back_with_clear_errors():
    from audit_rules.configuration import load_operational_settings

    settings, errors = load_operational_settings({
        "AUDIT_FETCH_TIMEOUT_SECONDS": "never",
        "AUDIT_FETCH_WORKERS": "1000",
        "AUDIT_REPORT_PDF_ENABLED": "sometimes",
    })

    assert settings["fetch_timeout_s"] == 20.0
    assert settings["fetch_workers"] == 4
    assert settings["report_pdf_enabled"] is True
    assert len(errors) == 3
    assert all("using default" in error for error in errors)
