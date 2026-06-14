from services.customer_matcher_service import CustomerMatcherService


def test_match_exact_returns_eindeutig_for_single_match():
    service = CustomerMatcherService()
    contacts = [
        {"Firmenname": "Musterkunde GmbH", "Kundennummer": "10001"},
    ]

    result = service.match_exact("  musterkunde gmbh  ", contacts)

    assert result.state == "eindeutig"
    assert result.customer_name == "Musterkunde GmbH"
    assert result.customer_number == "10001"


def test_match_exact_returns_mehrdeutig_for_multiple_matches():
    service = CustomerMatcherService()
    contacts = [
        {"Firmenname": "Musterkunde GmbH", "Kundennummer": "10001"},
        {"Firmenname": "Musterkunde GmbH", "Kundennummer": "10002"},
    ]

    result = service.match_exact("Musterkunde GmbH", contacts)

    assert result.state == "mehrdeutig"
    assert result.customer_name == "Musterkunde GmbH"
    assert result.customer_number == ""


def test_match_exact_returns_nicht_gefunden_when_missing():
    service = CustomerMatcherService()
    contacts = [{"Firmenname": "Andere Firma", "Kundennummer": "20001"}]

    result = service.match_exact("Musterkunde GmbH", contacts)

    assert result.state == "nicht_gefunden"
    assert result.customer_name == ""
    assert result.customer_number == ""


def test_match_exact_returns_nicht_zugeordnet_for_empty_input():
    service = CustomerMatcherService()

    result = service.match_exact("", [{"Firmenname": "X"}])

    assert result.state == "nicht_zugeordnet"


def test_match_exact_handles_punctuation_variation():
    service = CustomerMatcherService()
    contacts = [
        {"Firmenname": "Elektrotechnik Oelsnitz/E. GmbH", "Kundennummer": "10061"},
    ]

    result = service.match_exact("Elektrotechnik Oelsnitz./E. GmbH", contacts)

    assert result.state == "eindeutig"
    assert result.customer_number == "10061"


def test_match_exact_handles_legal_form_variation():
    service = CustomerMatcherService()
    contacts = [
        {"Firmenname": "Isoblock Schaltanlagen GmbH & Co. KG", "Kundennummer": "10003"},
    ]

    result = service.match_exact("Isoblock Schaltanlagen", contacts)

    assert result.state == "eindeutig"
    assert result.customer_number == "10003"


def test_match_exact_extracts_customer_address_fields():
    service = CustomerMatcherService()
    contacts = [
        {
            "Firmenname": "DIGITAL SOLAR SERVICE eGbR",
            "Kundennummer": "10057",
            "Straße 1": "Struthweg 28",
            "PLZ 1": "34260",
            "Ort 1": "Kaufungen",
            "Land 1": "DE",
        },
    ]

    result = service.match_exact("Digital Solar Service", contacts)

    assert result.state == "eindeutig"
    assert result.address_street == "Struthweg 28"
    assert result.address_zip == "34260"
    assert result.address_city == "Kaufungen"
    assert result.address_country == "DE"