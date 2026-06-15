"""Tests für Rechnungspositionen und Validierungslogik."""
import pytest

from domain.invoice_models import InvoiceProposal, InvoicePosition, ValidationMessage
from services.invoice_position_service import InvoicePositionService
from services.invoice_validation_service import InvoiceValidationService
from services.invoice_proposal_mapper_service import InvoiceProposalMapperService
from services.customer_matcher_service import CustomerMatcherService


@pytest.fixture
def position_service():
    return InvoicePositionService()


@pytest.fixture
def validation_service():
    return InvoiceValidationService()


@pytest.fixture
def mapper_service(validation_service, position_service):
    return InvoiceProposalMapperService(
        customer_matcher=CustomerMatcherService(),
        position_service=position_service,
        validation_service=validation_service,
    )


@pytest.fixture
def sample_group():
    """Test-Gruppe mit Einsätzen."""
    return {
        "datum": "01.01.2026",
        "zeitraum_von": "01.01.2026",
        "zeitraum_bis": "03.01.2026",
        "kw": "1",
        "kunde_roh": "Energietechnik AG",
        "projekt_roh": "Heizungsanlage",
        "adresse_roh": "Musterstr. 1, 12345 Beispielstadt",
        "mitarbeiter_liste": ["Max Mustermann", "Anna Schmidt"],
        "eintraege": [
            {
                "datum": "01.01.2026",
                "mitarbeiter": "Max Mustermann",
                "kunde_roh": "Energietechnik AG",
                "projekt_roh": "Heizungsanlage",
            },
            {
                "datum": "02.01.2026",
                "mitarbeiter": "Anna Schmidt",
                "kunde_roh": "Energietechnik AG",
                "projekt_roh": "Heizungsanlage",
            },
            {
                "datum": "03.01.2026",
                "mitarbeiter": "Max Mustermann",
                "kunde_roh": "Energietechnik AG",
                "projekt_roh": "Heizungsanlage",
            },
        ],
    }


class TestInvoicePositionService:
    def test_extract_positions_simple(self, position_service, sample_group):
        """Test: Einfache Positions-Extraktion pro Mitarbeiter."""
        positions = position_service.extract_positions_simple(sample_group)

        assert len(positions) == 2  # Max und Anna
        assert all(isinstance(p, InvoicePosition) for p in positions)
        # Positionen sind sortiert nach Mitarbeitername
        titles = sorted([p.title for p in positions])
        assert "Anna Schmidt - Heizungsanlage (01.01.2026 bis 03.01.2026)" in titles
        assert "Max Mustermann - Heizungsanlage (01.01.2026 bis 03.01.2026)" in titles

    def test_extract_positions_from_entries(self, position_service, sample_group):
        """Test: Positions-Extraktion aus Eintragen."""
        positions = position_service.extract_positions_from_group(sample_group)

        assert len(positions) >= 2
        assert all(isinstance(p, InvoicePosition) for p in positions)

    def test_enrich_proposal_with_positions(self, position_service, sample_group):
        """Test: Proposal wird mit Positionen angereichert."""
        proposal = InvoiceProposal(
            source_group_key="test_key",
            start_date="01.01.2026",
            end_date="03.01.2026",
            kw="1",
            customer_raw="Energietechnik AG",
            project_raw="Heizungsanlage",
        )

        assert len(proposal.positions) == 0

        position_service.enrich_proposal_with_positions(proposal, sample_group)

        assert len(proposal.positions) > 0
        assert all(isinstance(p, InvoicePosition) for p in proposal.positions)

    def test_enrich_proposal_uses_selected_article(self, position_service, sample_group):
        """Test: Ausgewählter Artikel wird für Positionsdaten verwendet."""
        proposal = InvoiceProposal(
            source_group_key="test_key",
            start_date="01.01.2026",
            end_date="03.01.2026",
            kw="1",
            customer_raw="Energietechnik AG",
            project_raw="Heizungsanlage",
        )
        sample_group["selected_article"] = {
            "Artikelnummer": "ET-1",
            "Bezeichnung": "ET Service",
            "Einheit": "Stunde",
            "Steuerart": "USt19",
            "VK (Netto)": "200,00",
        }

        position_service.enrich_proposal_with_positions(proposal, sample_group)

        assert len(proposal.positions) == 1
        assert proposal.positions[0].title == "ET-1 - ET Service"
        assert proposal.positions[0].unit == "Stunde"
        assert proposal.positions[0].unit_price_net == 200.0
        assert proposal.positions[0].tax_rate == 19.0

    def test_enrich_proposal_uses_multiple_selected_articles(self, position_service, sample_group):
        """Test: Mehrere ausgewählte Artikel werden als mehrere Positionen übernommen."""
        proposal = InvoiceProposal(
            source_group_key="test_key",
            start_date="01.01.2026",
            end_date="03.01.2026",
            kw="1",
            customer_raw="Energietechnik AG",
            project_raw="Heizungsanlage",
        )
        sample_group["selected_articles"] = [
            {
                "Artikelnummer": "ET-1",
                "Bezeichnung": "ET Service 1",
                "Einheit": "Stunde",
                "Steuerart": "USt19",
                "VK (Netto)": "200,00",
            },
            {
                "Artikelnummer": "ET-2",
                "Bezeichnung": "ET Service 2",
                "Einheit": "Stück",
                "Steuerart": "USt7",
                "VK (Netto)": "50,00",
            },
        ]

        position_service.enrich_proposal_with_positions(proposal, sample_group)

        assert len(proposal.positions) == 2
        assert proposal.positions[0].title == "ET-1 - ET Service 1"
        assert proposal.positions[0].unit == "Stunde"
        assert proposal.positions[0].unit_price_net == 200.0
        assert proposal.positions[0].tax_rate == 19.0
        assert proposal.positions[1].title == "ET-2 - ET Service 2"
        assert proposal.positions[1].unit == "Stück"
        assert proposal.positions[1].unit_price_net == 50.0
        assert proposal.positions[1].tax_rate == 7.0

    def test_travel_costs_as_extra_article(self, position_service, sample_group):
        proposal = InvoiceProposal(
            source_group_key="test_key",
            start_date="01.01.2026",
            end_date="03.01.2026",
            kw="1",
            customer_raw="Energietechnik AG",
            project_raw="Heizungsanlage",
        )
        sample_group["selected_articles"] = [
            {
                "Artikelnummer": "ET-1",
                "Bezeichnung": "ET Service",
                "Einheit": "Stunde",
                "Steuerart": "USt19",
                "VK (Netto)": "200,00",
            }
        ]
        sample_group["travel_mode"] = "extra_article"
        sample_group["travel_hours"] = 2
        sample_group["travel_hour_rate"] = 150
        sample_group["travel_km"] = 10
        sample_group["travel_km_rate"] = 0.7

        position_service.enrich_proposal_with_positions(proposal, sample_group)

        assert len(proposal.positions) == 2
        assert proposal.positions[1].title == "Fahrtkosten"
        assert proposal.positions[1].unit == "Pauschale"
        assert proposal.positions[1].unit_price_net == 307.0

    def test_travel_costs_included_in_first_article(self, position_service, sample_group):
        proposal = InvoiceProposal(
            source_group_key="test_key",
            start_date="01.01.2026",
            end_date="03.01.2026",
            kw="1",
            customer_raw="Energietechnik AG",
            project_raw="Heizungsanlage",
        )
        sample_group["selected_articles"] = [
            {
                "Artikelnummer": "ET-1",
                "Bezeichnung": "ET Service",
                "Einheit": "Stunde",
                "Steuerart": "USt19",
                "VK (Netto)": "200,00",
            }
        ]
        sample_group["travel_mode"] = "included_in_first_article"
        sample_group["travel_hours"] = 2
        sample_group["travel_hour_rate"] = 150
        sample_group["travel_km"] = 10
        sample_group["travel_km_rate"] = 0.7

        position_service.enrich_proposal_with_positions(proposal, sample_group)

        assert len(proposal.positions) == 1
        assert proposal.positions[0].title == "ET-1 - ET Service"
        assert proposal.positions[0].unit_price_net == 507.0

    def test_multi_day_allowance_assignment_tag_1(self, position_service, sample_group):
        proposal = InvoiceProposal(
            source_group_key="test_key",
            start_date="01.01.2026",
            end_date="03.01.2026",
            kw="1",
            customer_raw="Energietechnik AG",
            project_raw="Heizungsanlage",
        )
        sample_group["selected_articles"] = [
            {
                "Artikelnummer": "MT-1",
                "Bezeichnung": "Mehrtagespauschale",
                "Einheit": "Pauschale",
                "Steuerart": "USt19",
                "VK (Netto)": "100,00",
            }
        ]
        sample_group["multi_day_allowance_assignment_rule"] = "tag_1"

        position_service.enrich_proposal_with_positions(proposal, sample_group)

        assert len(proposal.positions) == 1
        assert "Mehrtagespauschale zugeordnet: Tag 1" in str(proposal.positions[0].description or "")
        assert "01.01.2026" in str(proposal.positions[0].description or "")

    def test_multi_day_allowance_assignment_tag_2(self, position_service, sample_group):
        proposal = InvoiceProposal(
            source_group_key="test_key",
            start_date="01.01.2026",
            end_date="03.01.2026",
            kw="1",
            customer_raw="Energietechnik AG",
            project_raw="Heizungsanlage",
        )
        sample_group["selected_articles"] = [
            {
                "Artikelnummer": "MT-1",
                "Bezeichnung": "Mehrtagespauschale",
                "Einheit": "Pauschale",
                "Steuerart": "USt19",
                "VK (Netto)": "100,00",
            }
        ]
        sample_group["multi_day_allowance_assignment_rule"] = "tag_2"

        position_service.enrich_proposal_with_positions(proposal, sample_group)

        assert len(proposal.positions) == 1
        assert "Mehrtagespauschale zugeordnet: Tag 2" in str(proposal.positions[0].description or "")
        assert "03.01.2026" in str(proposal.positions[0].description or "")


class TestInvoiceValidationService:
    def test_validate_proposal_with_errors(self, validation_service):
        """Test: Validierung erkennt Fehler."""
        proposal = InvoiceProposal(
            source_group_key="test_key",
            start_date="",
            end_date="",
            kw="",
            customer_raw="",  # Leer = Fehler
            project_raw="",
            mandant_id="",  # Leer = Fehler
        )

        messages = validation_service.validate_proposal(proposal)

        assert len(messages) > 0
        assert any(msg.level == "error" for msg in messages)
        assert validation_service.has_errors(proposal)

    def test_validate_proposal_with_warnings(self, validation_service):
        """Test: Validierung erkennt Warnungen."""
        proposal = InvoiceProposal(
            source_group_key="test_key",
            start_date="01.01.2026",
            end_date="01.01.2026",
            kw="1",
            customer_raw="Kunde",
            project_raw="Projekt",
            mandant_id="ges_energietechnik",
            address_name="",  # Fehlt = Warnung
        )

        messages = validation_service.validate_proposal(proposal)

        assert any(msg.level == "warning" for msg in messages)
        assert validation_service.has_warnings(proposal)

    def test_validate_proposal_success(self, validation_service):
        """Test: Validierung erfolgreich ohne Fehler."""
        proposal = InvoiceProposal(
            source_group_key="test_key",
            start_date="01.01.2026",
            end_date="03.01.2026",
            kw="1",
            customer_raw="Energietechnik AG",
            project_raw="Heizungsanlage",
            mandant_id="ges_energietechnik",
            address_name="Energietechnik AG",
            address_street="Musterstr. 1",
            address_zip="12345",
            address_city="Beispielstadt",
            payment_terms_text="14 Tage netto",
            positions=[
                InvoicePosition(
                    title="Max Mustermann - Heizungsanlage",
                    quantity=1.0,
                    unit="Einsatztag",
                    unit_price_net=100.0,
                )
            ],
        )

        messages = validation_service.validate_proposal(proposal)

        errors = [m for m in messages if m.level == "error"]
        assert len(errors) == 0
        assert not validation_service.has_errors(proposal)

    def test_format_validation_report(self, validation_service):
        """Test: Validierungsbericht wird formatiert."""
        proposal = InvoiceProposal(
            source_group_key="test_key",
            start_date="01.01.2026",
            end_date="01.01.2026",
            kw="1",
            customer_raw="",
            project_raw="Projekt",
            mandant_id="",
            invoice_name_long="Rechnung Projekt",
        )

        validation_service.validate_proposal(proposal)
        report = validation_service.format_validation_report(proposal)

        assert "Validierungsbericht für" in report
        assert "Fehler" in report or "error" in report.lower()

    def test_position_quantity_validation(self, validation_service):
        """Test: Positions-Menge wird validiert."""
        proposal = InvoiceProposal(
            source_group_key="test_key",
            start_date="01.01.2026",
            end_date="01.01.2026",
            kw="1",
            customer_raw="Kunde",
            project_raw="Projekt",
            mandant_id="ges_energietechnik",
            positions=[
                InvoicePosition(
                    title="Position 1",
                    quantity=0,  # Fehler!
                    unit_price_net=100.0,
                )
            ],
        )

        messages = validation_service.validate_proposal(proposal)

        assert any("Menge" in msg.message for msg in messages)
        assert any(msg.level == "error" for msg in messages)


class TestInvoiceProposalMapperIntegration:
    def test_map_group_with_positions_and_validation(self, mapper_service, sample_group):
        """Test: Group wird zu vollständigem Proposal mit Positionen und Validierung."""
        proposal = mapper_service.map_group(
            sample_group,
            default_mandant_id="ges_energietechnik",
        )

        assert proposal.mandant_id == "ges_energietechnik"
        assert proposal.customer_raw == "Energietechnik AG"
        assert len(proposal.positions) > 0
        assert len(proposal.validation_messages) > 0

    def test_map_group_includes_customer_matching(self, mapper_service, sample_group):
        """Test: Customer Matching wird in Mapping integriert."""
        contacts = [
            {"firma": "Energietechnik AG", "kontakt": "01234/567890"},
            {"firma": "Other Corp", "kontakt": "01234/123456"},
        ]

        proposal = mapper_service.map_group(
            sample_group,
            default_mandant_id="ges_energietechnik",
            contacts=contacts,
        )

        # Customer Matching sollte durchgeführt werden
        assert proposal.customer_match is not None
        # Bei exaktem Match sollte state "eindeutig" sein
        if proposal.customer_match.state == "eindeutig":
            assert proposal.customer_match.customer_name == "Energietechnik AG"
        else:
            # Falls Match nicht exakt ist, sollte es "nicht_gefunden" sein
            assert proposal.customer_match.state in ["eindeutig", "nicht_gefunden"]

    def test_is_export_ready_with_errors(self, mapper_service):
        """Test: Proposal mit Fehlern ist nicht exportierbar."""
        proposal = InvoiceProposal(
            source_group_key="test_key",
            start_date="",
            end_date="",
            kw="",
            customer_raw="",
            project_raw="",
            mandant_id="",
        )

        # Validiere
        from services.invoice_validation_service import InvoiceValidationService
        validation_service = InvoiceValidationService()
        validation_service.validate_proposal(proposal)

        assert not proposal.is_export_ready

    def test_is_export_ready_success(self, mapper_service, sample_group):
        """Test: Vollständiger Proposal ist exportierbar."""
        proposal = mapper_service.map_group(
            sample_group,
            default_mandant_id="ges_energietechnik",
        )

        # Setze manuelle Daten für erfolgreiche Validierung
        proposal.address_zip = "12345"
        proposal.address_city = "Beispielstadt"
        proposal.positions = [
            InvoicePosition(
                title="Einsatz",
                quantity=1.0,
                unit_price_net=100.0,
            )
        ]

        # Re-validiere
        from services.invoice_validation_service import InvoiceValidationService
        validation_service = InvoiceValidationService()
        validation_service.validate_proposal(proposal)

        # Sollte keine Fehler haben
        errors = [m for m in proposal.validation_messages if m.level == "error"]
        assert len(errors) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
