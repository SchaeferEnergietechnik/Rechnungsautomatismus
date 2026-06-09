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