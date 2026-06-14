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
