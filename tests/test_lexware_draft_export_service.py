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

    assert payload["title"] == "Angebot"
    assert "expirationDate" in payload
    assert str(payload["expirationDate"]).strip() != ""


def test_invoice_payload_has_no_expiration_date(monkeypatch):
    monkeypatch.setenv("LEXWARE_DRAFT_ENDPOINT", "/v1/invoices")
    service = LexwareDraftExportService()

    payload = service._build_payload(_sample_group())

    assert payload["title"] == "Rechnung"
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
    assert "10.00 km" in payload["lineItems"][1]["description"]


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
    assert "2.00 h" in payload["lineItems"][0]["description"]
