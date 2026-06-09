from services.invoice_proposal_mapper_service import InvoiceProposalMapperService


def test_maps_group_to_invoice_proposal_with_defaults():
    service = InvoiceProposalMapperService()
    group = {
        "datum": "2026-06-01",
        "zeitraum_von": "2026-06-01",
        "zeitraum_bis": "2026-06-03",
        "kw": "23",
        "kunde_roh": "Musterkunde GmbH",
        "projekt_roh": "Projekt Nord",
        "adresse_roh": "Musterstrasse 2",
        "mitarbeiter_liste": ["Anna", "Anna", "Ben"],
    }

    proposal = service.map_group(group, default_mandant_id="ges_energietechnik")

    assert proposal.mandant_id == "ges_energietechnik"
    assert proposal.start_date == "2026-06-01"
    assert proposal.end_date == "2026-06-03"
    assert proposal.customer_raw == "Musterkunde GmbH"
    assert proposal.voucher_title_lexware.startswith("Rechnung")
    assert len(proposal.voucher_title_lexware) <= 25
    assert proposal.employees == ["Anna", "Ben"]


def test_maps_customer_match_when_contacts_provided():
    service = InvoiceProposalMapperService()
    group = {
        "datum": "2026-06-01",
        "kunde_roh": "Musterkunde GmbH",
        "projekt_roh": "Projekt Nord",
    }
    contacts = [
        {"Firmenname": "Musterkunde GmbH", "Kundennummer": "10001"},
    ]

    proposal = service.map_group(group, contacts=contacts)

    assert proposal.customer_match.state == "eindeutig"
    assert proposal.customer_match.customer_name == "Musterkunde GmbH"
    assert proposal.customer_match.customer_number == "10001"
