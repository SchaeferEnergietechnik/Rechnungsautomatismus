from services.lexware_draft_export_service import LexwareDraftExportService


def _sample_group() -> dict:
    return {
        "datum": "2026-04-07 00:00:00",
        "kunde_roh": "Testkunde GmbH",
        "projekt_roh": "Projekt X",
        "adresse_roh": "Musterstrasse 1",
        "bemerkungen_roh": "Hinweis",
        "mitarbeiter_liste": ["Max Mustermann"],
    }


def test_default_endpoint_is_quotations(monkeypatch):
    monkeypatch.delenv("LEXWARE_DRAFT_ENDPOINT", raising=False)
    service = LexwareDraftExportService()
    assert service.draft_endpoint == "/v1/quotations"


def test_payload_contains_required_payment_fields(monkeypatch):
    monkeypatch.setenv("LEXWARE_PAYMENT_TERM_DAYS", "21")
    service = LexwareDraftExportService()

    payload = service._build_payload(_sample_group())

    assert payload["paymentConditions"]["paymentTermDuration"] == 21
    assert payload["paymentConditions"]["paymentTermLabel"] == "21 Tage netto"


def test_payload_uses_overrides(monkeypatch):
    monkeypatch.setenv("LEXWARE_DRAFT_ENDPOINT", "/v1/quotations")
    service = LexwareDraftExportService()

    payload = service._build_payload(
        _sample_group(),
        title="Sonderangebot",
        introduction="Individuelle Einleitung",
        remark="Individuelle Nachbemerkung",
        payment_term_days=30,
        payment_term_label="30 Tage netto",
    )

    assert payload["title"] == "Sonderangebot"
    assert payload["introduction"] == "Individuelle Einleitung"
    assert payload["remark"] == "Individuelle Nachbemerkung"
    assert payload["paymentConditions"]["paymentTermDuration"] == 30
    assert payload["paymentConditions"]["paymentTermLabel"] == "30 Tage netto"
    assert "expirationDate" in payload


def test_payload_line_items_shape(monkeypatch):
    monkeypatch.delenv("LEXWARE_DRAFT_ENDPOINT", raising=False)
    service = LexwareDraftExportService()

    payload = service._build_payload(_sample_group())
    assert isinstance(payload["lineItems"], list)
    assert payload["lineItems"][0]["unitPrice"]["taxRatePercentage"] == service.default_tax_rate


def test_quotation_payload_contains_expiration_date(monkeypatch):
    monkeypatch.setenv("LEXWARE_DRAFT_ENDPOINT", "/v1/quotations")
    monkeypatch.setenv("LEXWARE_PAYMENT_TERM_DAYS", "14")
    service = LexwareDraftExportService()

    payload = service._build_payload(_sample_group())

    assert payload["title"].startswith("Angebot - ")
    assert "expirationDate" in payload
    assert str(payload["expirationDate"]).strip() != ""


def test_invoice_payload_has_no_expiration_date(monkeypatch):
    monkeypatch.setenv("LEXWARE_DRAFT_ENDPOINT", "/v1/invoices")
    service = LexwareDraftExportService()

    payload = service._build_payload(_sample_group())

    assert payload["title"].startswith("Rechnung - ")
    assert "expirationDate" not in payload


def test_payload_variants_include_nested_fallback():
    service = LexwareDraftExportService()
    variants = service._build_payload_variants(_sample_group())

    assert isinstance(variants, list)
    assert len(variants) == 2
    assert isinstance(variants[0]["lineItems"], list)
    assert isinstance(variants[1]["lineItems"], dict)
    assert "lineItems" in variants[1]["lineItems"]


def test_detects_lineitems_validation_error():
    service = LexwareDraftExportService()
    result = {
        "status_code": 400,
        "response": {"message": "Invalid data received for field 'lineItems'."},
    }
    assert service._is_lineitems_validation_error(result) is True


def test_fetch_customers_normalizes_list(monkeypatch):
    service = LexwareDraftExportService()
    service.is_configured = lambda: True
    service.access_token = "token"
    service._get_json = lambda url, company_id="", _retried=False: {
        "success": True,
        "status_code": 200,
        "error": "",
        "response": {
            "content": [
                {"id": "c1", "customerNumber": "1001", "name": "Alpha GmbH"},
                {"id": "c2", "number": "1002", "displayName": "Beta GmbH"},
            ]
        },
    }

    result = service.fetch_customers(company_id="company-x")

    assert result["success"] is True
    assert len(result["customers"]) == 2
    assert result["customers"][0]["customer_number"] == "1001"
    assert result["customers"][1]["name"] == "Beta GmbH"


def test_fetch_customers_loads_multiple_pages():
    service = LexwareDraftExportService()
    service.is_configured = lambda: True
    service.access_token = "token"

    def _fake_get_json(url, company_id="", _retried=False):
        if "page=0" in url:
            return {
                "success": True,
                "status_code": 200,
                "error": "",
                "response": {
                    "content": [
                        {"id": "c1", "customerNumber": "1001", "name": "Alpha GmbH"},
                    ],
                    "totalPages": 2,
                },
            }
        return {
            "success": True,
            "status_code": 200,
            "error": "",
            "response": {
                "content": [
                    {"id": "c2", "customerNumber": "1002", "name": "Zeta GmbH"},
                ],
                "totalPages": 2,
            },
        }

    service._get_json = _fake_get_json

    result = service.fetch_customers(company_id="company-x")

    assert result["success"] is True
    assert len(result["customers"]) == 2
    assert result["customers"][0]["name"] == "Alpha GmbH"
    assert result["customers"][1]["name"] == "Zeta GmbH"


def test_fetch_text_templates_filters_customer(monkeypatch):
    service = LexwareDraftExportService()
    service.is_configured = lambda: True
    service.access_token = "token"
    service._get_json = lambda url, company_id="", _retried=False: {
        "success": True,
        "status_code": 200,
        "error": "",
        "response": {
            "items": [
                {
                    "id": "t1",
                    "name": "Standard",
                    "introduction": "Intro A",
                    "remark": "Remark A",
                    "customerNumber": "1001",
                    "voucherType": "quotation",
                },
                {
                    "id": "t2",
                    "name": "Global",
                    "introduction": "Intro B",
                    "remark": "Remark B",
                    "voucherType": "quotation",
                },
            ]
        },
    }

    result = service.fetch_text_templates(voucher_type="quotation", customer_number="1001")

    assert result["success"] is True
    assert len(result["templates"]) == 2
    assert result["templates"][0]["name"] == "Standard"


def test_payload_includes_travel_text_in_extra_article_description():
    service = LexwareDraftExportService()
    group = _sample_group()
    group["selected_articles"] = [
        {
            "Artikelnummer": "ET-1",
            "Bezeichnung": "Service",
            "Einheit": "Stunde",
            "Steuerart": "USt19",
            "VK (Netto)": "200,00",
        }
    ]
    group["travel_mode"] = "extra_article"
    group["travel_hours"] = 2
    group["travel_hour_rate"] = 150
    group["travel_km"] = 10
    group["travel_km_rate"] = 0.7

    payload = service._build_payload(group)

    assert len(payload["lineItems"]) == 2
    assert "Fahrtkostenangaben" not in payload["lineItems"][0]["description"]
    assert "Fahrtkostenangaben" in payload["lineItems"][1]["description"]
    assert payload["lineItems"][1]["description"].count("Fahrtkostenangaben") == 1
    assert "10 km" in payload["lineItems"][1]["description"]
    assert "EUR" not in payload["lineItems"][1]["description"]


def test_payload_includes_travel_text_in_first_article_description_when_included():
    service = LexwareDraftExportService()
    group = _sample_group()
    group["selected_articles"] = [
        {
            "Artikelnummer": "ET-1",
            "Bezeichnung": "Service",
            "Einheit": "Stunde",
            "Steuerart": "USt19",
            "VK (Netto)": "200,00",
        }
    ]
    group["travel_mode"] = "included_in_first_article"
    group["travel_hours"] = 2
    group["travel_hour_rate"] = 150
    group["travel_km"] = 10
    group["travel_km_rate"] = 0.7

    payload = service._build_payload(group)

    assert len(payload["lineItems"]) == 1
    assert "Fahrtkostenangaben" in payload["lineItems"][0]["description"]
    assert payload["lineItems"][0]["description"].count("Fahrtkostenangaben") == 1
    assert "2.00 h" in payload["lineItems"][0]["description"]
    assert "EUR" not in payload["lineItems"][0]["description"]


def test_fetch_text_templates_accepts_text_module_shape():
    service = LexwareDraftExportService()
    service.is_configured = lambda: True
    service.access_token = "token"
    service._get_json = lambda url, company_id="", _retried=False: {
        "success": True,
        "status_code": 200,
        "error": "",
        "response": {
            "textModules": [
                {
                    "id": "m1",
                    "name": "Intro Modul",
                    "moduleType": "introduction",
                    "text": "Intro Text",
                }
            ]
        },
    }

    result = service.fetch_text_templates(voucher_type="quotation")

    assert result["success"] is True
    assert len(result["templates"]) == 1
    assert result["templates"][0]["introduction"] == "Intro Text"


def test_fetch_text_templates_retries_without_voucher_type_filter():
    service = LexwareDraftExportService()
    service.is_configured = lambda: True
    service.access_token = "token"

    calls = {"count": 0}

    def _fake_get_json(url, company_id="", _retried=False):
        calls["count"] += 1
        if "voucherType=" in url:
            return {
                "success": True,
                "status_code": 200,
                "error": "",
                "response": {"items": []},
            }
        return {
            "success": True,
            "status_code": 200,
            "error": "",
            "response": {
                "items": [
                    {
                        "id": "t-fallback",
                        "name": "Fallback Vorlage",
                        "introduction": "Fallback Intro",
                    }
                ]
            },
        }

    service._get_json = _fake_get_json

    result = service.fetch_text_templates(voucher_type="quotation")

    assert result["success"] is True
    assert len(result["templates"]) == 1
    assert result["templates"][0]["name"] == "Fallback Vorlage"
    assert calls["count"] == 2


def test_fetch_text_templates_loads_multiple_pages():
    service = LexwareDraftExportService()
    service.is_configured = lambda: True
    service.access_token = "token"

    def _fake_get_json(url, company_id="", _retried=False):
        if "page=0" in url:
            return {
                "success": True,
                "status_code": 200,
                "error": "",
                "response": {
                    "items": [
                        {"id": "t1", "name": "Vorlage A", "introduction": "A"},
                    ],
                    "totalPages": 2,
                },
            }
        return {
            "success": True,
            "status_code": 200,
            "error": "",
            "response": {
                "items": [
                    {"id": "t2", "name": "Vorlage B", "remark": "B"},
                ],
                "totalPages": 2,
            },
        }

    service._get_json = _fake_get_json
    result = service.fetch_text_templates(voucher_type="quotation")

    assert result["success"] is True
    assert len(result["templates"]) == 2
    assert result["templates"][0]["name"] == "Vorlage A"
    assert result["templates"][1]["name"] == "Vorlage B"


def test_fetch_text_templates_keeps_name_only_templates():
    service = LexwareDraftExportService()
    service.is_configured = lambda: True
    service.access_token = "token"
    service._get_json = lambda url, company_id="", _retried=False: {
        "success": True,
        "status_code": 200,
        "error": "",
        "response": {
            "items": [
                {"id": "t-name-only", "name": "Nur Name"},
            ]
        },
    }

    result = service.fetch_text_templates(voucher_type="quotation")

    assert result["success"] is True
    assert len(result["templates"]) == 1
    assert result["templates"][0]["name"] == "Nur Name"


def test_build_update_url_from_resource_uri():
    service = LexwareDraftExportService()
    service.base_url = "https://api.lexware.io"
    service.draft_endpoint = "/v1/quotations"

    absolute = service._build_update_url("https://api.lexware.io/v1/quotations/abc")
    relative = service._build_update_url("/v1/quotations/abc")
    by_id = service._build_update_url("abc")

    assert absolute == "https://api.lexware.io/v1/quotations/abc"
    assert relative == "https://api.lexware.io/v1/quotations/abc"
    assert by_id == "https://api.lexware.io/v1/quotations/abc"


def test_export_group_as_draft_uses_update_when_requested():
    service = LexwareDraftExportService()
    service.is_configured = lambda: True
    service.access_token = "token"
    service.base_url = "https://api.lexware.io"
    service.draft_endpoint = "/v1/quotations"
    service._build_payload_variants = lambda *args, **kwargs: [{"title": "x"}]

    calls = {"update": 0, "post": 0}

    def _fake_update(url, payload, company_id=""):
        calls["update"] += 1
        assert url.endswith("/v1/quotations/existing-1")
        return {"success": True, "status_code": 200, "error": "", "response": {"id": "existing-1"}, "payload": payload}

    def _fake_post(url, payload, company_id=""):
        calls["post"] += 1
        return {"success": True, "status_code": 200, "error": "", "response": {"id": "new-1"}, "payload": payload}

    service._update_draft = _fake_update
    service._post_draft = _fake_post

    result = service.export_group_as_draft(
        _sample_group(),
        update_existing=True,
        export_reference="existing-1",
    )

    assert result["success"] is True
    assert calls["update"] == 1
    assert calls["post"] == 0


def test_payload_preserves_article_description_text():
    service = LexwareDraftExportService()
    group = _sample_group()
    group["selected_articles"] = [
        {
            "Artikelnummer": "ET-1",
            "Bezeichnung": "Service",
            "Beschreibung": "Originale Artikelbeschreibung",
            "Notiz": "Interne Notiz aus Artikel",
            "Einheit": "Stunde",
            "Steuerart": "USt19",
            "VK (Netto)": "200,00",
        }
    ]

    payload = service._build_payload(group)

    assert len(payload["lineItems"]) == 1
    assert "Originale Artikelbeschreibung" in payload["lineItems"][0]["description"]
    assert "Interne Notiz aus Artikel" in payload["lineItems"][0]["description"]
    assert "Projekt:" not in payload["lineItems"][0]["description"]


def test_payload_uses_matched_customer_address_instead_of_project_address():
    service = LexwareDraftExportService()
    group = _sample_group()
    group["adresse_roh"] = "Projektadresse 42, 99999 Baustelle"
    group["customer_match_name"] = "DIGITAL SOLAR SERVICE eGbR"
    group["customer_match_street"] = "Struthweg 28"
    group["customer_match_zip"] = "34260"
    group["customer_match_city"] = "Kaufungen"
    group["customer_match_country"] = "DE"

    payload = service._build_payload(group)

    assert payload["address"]["name"] == "DIGITAL SOLAR SERVICE eGbR"
    assert payload["address"]["street"] == "Struthweg 28"
    assert payload["address"]["zip"] == "34260"
    assert payload["address"]["city"] == "Kaufungen"
    assert payload["address"]["street"] != "Projektadresse 42, 99999 Baustelle"


def test_payload_title_includes_project_name():
    service = LexwareDraftExportService()
    group = _sample_group()
    group["adresse_roh"] = "Neutraubling"
    group["projekt_roh"] = "Projekt Alpha"
    group["selected_articles"] = [
        {
            "Artikelnummer": "ET-1",
            "Bezeichnung": "Service",
            "Einheit": "Stunde",
            "Steuerart": "USt19",
            "VK (Netto)": "200,00",
        }
    ]

    payload = service._build_payload(group)

    assert "Projekt Alpha" in payload["title"]
    assert payload["title"] == "Angebot - Projekt Alpha"


def test_travel_detail_text_reflects_segment_role_first_invoice():
    from services.invoice_position_service import InvoicePositionService
    
    position_service = InvoicePositionService()
    group = {
        "travel_hours": 1.5,
        "travel_km": 30.0,
        "travel_segment_role": "first_invoice_outbound",
        "travel_route_segments": ["Firma -> Neutraubling"],
    }

    text = position_service.travel_detail_text(group)

    assert "Anfahrt" in text
    assert "Firma -> Neutraubling" in text
    assert "1.50 h" in text
    assert "30 km" in text


def test_travel_detail_text_reflects_segment_role_middle_invoice():
    from services.invoice_position_service import InvoicePositionService
    
    position_service = InvoicePositionService()
    group = {
        "travel_hours": 0.25,
        "travel_km": 10.0,
        "travel_segment_role": "middle_invoice",
        "travel_route_segments": ["Neutraubling -> Vohenstrauß"],
    }

    text = position_service.travel_detail_text(group)

    assert "Zwischenfahrt" in text
    assert "Neutraubling -> Vohenstrauß" in text
    assert "0.25 h" in text
    assert "10 km" in text


def test_travel_detail_text_reflects_segment_role_last_invoice():
    from services.invoice_position_service import InvoicePositionService
    
    position_service = InvoicePositionService()
    group = {
        "travel_hours": 0.75,
        "travel_km": 20.0,
        "travel_segment_role": "last_invoice_with_return",
        "travel_route_segments": ["Vohenstrauß -> Firma (inkl. Rueckfahrt zur Firma)"],
    }

    text = position_service.travel_detail_text(group)

    assert "Rückfahrt" in text
    assert "Vohenstrauß" in text
    assert "0.75 h" in text
    assert "20 km" in text


def test_payload_description_omits_employee_names():
    service = LexwareDraftExportService()
    payload = service._build_payload(_sample_group())

    description = str(payload["lineItems"][0].get("description", "") or "")
    assert "Mitarbeiter:" not in description
    assert "Max Mustermann" not in description


def test_export_group_uses_invoice_endpoint_and_finalize_query():
    service = LexwareDraftExportService()
    service.is_configured = lambda: True
    service.access_token = "token"
    service.base_url = "https://api.lexware.test"

    captured = {}

    def _fake_post(url, payload, company_id=""):
        captured["url"] = url
        return {
            "success": True,
            "status_code": 201,
            "error": "",
            "response": {"id": "new-1"},
            "payload": payload,
        }

    service._post_draft = _fake_post

    result = service.export_group_as_draft(
        _sample_group(),
        voucher_type="invoice",
        finalize=True,
    )

    assert result["success"] is True
    assert "/v1/invoices" in captured["url"]
    assert "finalize=true" in captured["url"]


def test_auto_title_template_is_recomputed_per_group():
    service = LexwareDraftExportService()

    first_group = _sample_group()
    first_group["projekt_roh"] = "Neutraubling"
    first_payload = service._build_payload(first_group, title="Angebot - Neutraubling")

    second_group = _sample_group()
    second_group["projekt_roh"] = "Vohenstrauß"
    second_payload = service._build_payload(second_group, title="Angebot - Neutraubling")

    assert first_payload["title"] == "Angebot - Neutraubling"
    assert second_payload["title"] == "Angebot - Vohenstrauß"


def test_build_web_url_with_template(monkeypatch):
    monkeypatch.setenv("LEXWARE_WEB_URL_TEMPLATE", "https://app.lexoffice.de/vouchers/{id}")
    service = LexwareDraftExportService()

    # resourceUri enthält UUID am Ende
    url = service.build_web_url("https://api.lexware.io/v1/quotations/abc-123")
    assert url == "https://app.lexoffice.de/vouchers/abc-123"

    # bare ID
    url = service.build_web_url("uuid-456")
    assert url == "https://app.lexoffice.de/vouchers/uuid-456"


def test_build_web_url_fallback_to_resource_uri(monkeypatch):
    monkeypatch.delenv("LEXWARE_WEB_URL_TEMPLATE", raising=False)
    service = LexwareDraftExportService()

    # resourceUri ist direkt nutzbar wenn HTTP-URL
    url = service.build_web_url("https://api.lexware.io/v1/quotations/abc-123")
    assert url == "https://api.lexware.io/v1/quotations/abc-123"

    # bare ID ohne URL-Präfix → kein Fallback
    url = service.build_web_url("uuid-456")
    assert url == ""

    # leer → leer
    assert service.build_web_url("") == ""
