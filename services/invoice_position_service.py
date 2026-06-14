"""Service zur Extraktion von Rechnungspositionen aus Einsatzgruppen."""
from domain.invoice_models import InvoicePosition, InvoiceProposal


class InvoicePositionService:
    """Extrahiert und strukturiert Rechnungspositionen aus Einsatzgruppen."""

    def extract_positions_from_group(self, group: dict) -> list[InvoicePosition]:
        """Extrahiert Positionen aus einer Gruppe (= mehrere Einsätze).
        
        Strategie:
        - Pro Mitarbeiter + Tag eine Position
        - Position enthält: Mitarbeiter, Datum, Projektbeschreibung
        """
        positions: list[InvoicePosition] = []
        entries = group.get("eintraege", [])

        if not entries:
            return positions

        # Gruppiere Einträge pro Mitarbeiter+Datum
        by_employee_date: dict[tuple, dict] = {}

        for entry in entries:
            employee = str(entry.get("mitarbeiter", "")).strip()
            datum = str(entry.get("datum", "")).strip()
            key = (employee, datum)

            if key not in by_employee_date:
                by_employee_date[key] = entry
            else:
                # Falls mehrere Einträge pro Tag pro Mitarbeiter, akkumuliere
                pass

        # Erstelle Positionen
        for (employee, datum), entry in sorted(by_employee_date.items()):
            title = self._build_position_title(employee, datum, group)
            position = InvoicePosition(
                title=title,
                quantity=1.0,
                unit="Einsatztag",
                unit_price_net=0.0,  # wird später aus Tarif/Kalkulation gefüllt
            )
            positions.append(position)

        return positions

    def extract_positions_simple(self, group: dict) -> list[InvoicePosition]:
        """Einfachere Variante: eine Position pro Mitarbeiter."""
        positions: list[InvoicePosition] = []
        employees = group.get("mitarbeiter_liste", [])
        project = str(group.get("projekt_roh", "")).strip() or "Leistung"
        datum_von = str(group.get("zeitraum_von", "")).strip()
        datum_bis = str(group.get("zeitraum_bis", "")).strip()

        date_range = f"{datum_von} bis {datum_bis}" if datum_von != datum_bis else datum_von

        for employee in employees:
            title = f"{employee} - {project} ({date_range})"
            position = InvoicePosition(
                title=title,
                quantity=1.0,
                unit="Einsatztag",
                unit_price_net=0.0,
            )
            positions.append(position)

        return positions

    def _build_position_title(self, employee: str, datum: str, group: dict) -> str:
        """Erstellt einen aussagekräftigen Positionstitel."""
        project = str(group.get("projekt_roh", "")).strip() or "Leistung"
        return f"{employee} - {project} ({datum})"

    def enrich_proposal_with_positions(
        self,
        proposal: InvoiceProposal,
        group: dict,
    ) -> None:
        """Fügt Positionen zu einem Proposal hinzu."""
        positions = self.extract_positions_simple(group)
        proposal.positions = positions
