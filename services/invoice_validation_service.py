"""Service zur Validierung von Rechnungsentwürfen."""
from domain.invoice_models import InvoiceProposal, ValidationMessage


class InvoiceValidationService:
    """Validiert Rechnungsentwürfe auf Vollständigkeit und Konsistenz."""

    def validate_proposal(self, proposal: InvoiceProposal) -> list[ValidationMessage]:
        """Führt vollständige Validierung durch."""
        messages: list[ValidationMessage] = []

        # Pflichtfelder
        messages.extend(self._validate_required_fields(proposal))

        # Kundenzuordnung
        messages.extend(self._validate_customer_match(proposal))

        # Adressen
        messages.extend(self._validate_address(proposal))

        # Positionen
        messages.extend(self._validate_positions(proposal))

        # Zahlung
        messages.extend(self._validate_payment_terms(proposal))

        proposal.validation_messages = messages
        return messages

    def _validate_required_fields(self, proposal: InvoiceProposal) -> list[ValidationMessage]:
        """Validiert Pflichtfelder."""
        messages: list[ValidationMessage] = []

        if not proposal.mandant_id:
            messages.append(ValidationMessage(
                level="error",
                field="mandant_id",
                message="Mandant ist nicht gesetzt",
            ))

        if not proposal.customer_raw or proposal.customer_raw.lower() in ["unbekannt", "n/a", ""]:
            messages.append(ValidationMessage(
                level="error",
                field="customer_raw",
                message="Kunde ist nicht gesetzt oder unbekannt",
            ))

        if not proposal.start_date:
            messages.append(ValidationMessage(
                level="error",
                field="start_date",
                message="Startdatum ist nicht gesetzt",
            ))

        if not proposal.invoice_name_long or proposal.invoice_name_long.lower() in ["rechnung", ""]:
            messages.append(ValidationMessage(
                level="warning",
                field="invoice_name_long",
                message="Rechnungsname ist zu generisch",
            ))

        return messages

    def _validate_customer_match(self, proposal: InvoiceProposal) -> list[ValidationMessage]:
        """Validiert Kundenzuordnung."""
        messages: list[ValidationMessage] = []

        match = proposal.customer_match
        if match.state == "nicht_zugeordnet":
            messages.append(ValidationMessage(
                level="warning",
                field="customer_match",
                message="Kunde ist nicht zugeordnet",
            ))
        elif match.state == "nicht_gefunden":
            messages.append(ValidationMessage(
                level="warning",
                field="customer_match",
                message="Kunde nicht in Kundenstamm gefunden",
            ))
        elif match.state == "mehrdeutig":
            messages.append(ValidationMessage(
                level="warning",
                field="customer_match",
                message="Kunde ist mehrdeutig - manuelle Zuordnung notwendig",
            ))

        return messages

    def _validate_address(self, proposal: InvoiceProposal) -> list[ValidationMessage]:
        """Validiert Adressinformationen."""
        messages: list[ValidationMessage] = []

        if not proposal.address_name or proposal.address_name.lower() in ["unbekannt", "n/a", ""]:
            messages.append(ValidationMessage(
                level="warning",
                field="address_name",
                message="Adressname fehlt oder ist unbekannt",
            ))

        if not proposal.address_street:
            messages.append(ValidationMessage(
                level="warning",
                field="address_street",
                message="Straße ist nicht gesetzt",
            ))

        if not proposal.address_zip:
            messages.append(ValidationMessage(
                level="info",
                field="address_zip",
                message="Postleitzahl fehlt",
            ))

        if not proposal.address_city:
            messages.append(ValidationMessage(
                level="info",
                field="address_city",
                message="Stadt fehlt",
            ))

        return messages

    def _validate_positions(self, proposal: InvoiceProposal) -> list[ValidationMessage]:
        """Validiert Rechnungspositionen."""
        messages: list[ValidationMessage] = []

        if not proposal.positions:
            messages.append(ValidationMessage(
                level="error",
                field="positions",
                message="Keine Rechnungspositionen vorhanden",
            ))
            return messages

        for i, pos in enumerate(proposal.positions):
            if not pos.title or pos.title.lower() in ["", "position"]:
                messages.append(ValidationMessage(
                    level="warning",
                    field=f"position_{i}_title",
                    message=f"Position {i + 1}: Beschreibung fehlt oder ist zu generisch",
                ))

            if pos.quantity <= 0:
                messages.append(ValidationMessage(
                    level="error",
                    field=f"position_{i}_quantity",
                    message=f"Position {i + 1}: Menge muss größer als 0 sein",
                ))

            if pos.unit_price_net < 0:
                messages.append(ValidationMessage(
                    level="error",
                    field=f"position_{i}_price",
                    message=f"Position {i + 1}: Preis kann nicht negativ sein",
                ))

        return messages

    def _validate_payment_terms(self, proposal: InvoiceProposal) -> list[ValidationMessage]:
        """Validiert Zahlungsbedingungen."""
        messages: list[ValidationMessage] = []

        if not proposal.payment_terms_text:
            messages.append(ValidationMessage(
                level="warning",
                field="payment_terms_text",
                message="Zahlungsbedingungen sind nicht gesetzt",
            ))

        return messages

    def has_errors(self, proposal: InvoiceProposal) -> bool:
        """Prüft, ob es Fehler gibt."""
        return any(msg.level == "error" for msg in proposal.validation_messages)

    def has_warnings(self, proposal: InvoiceProposal) -> bool:
        """Prüft, ob es Warnungen gibt."""
        return any(msg.level == "warning" for msg in proposal.validation_messages)

    def format_validation_report(self, proposal: InvoiceProposal) -> str:
        """Erstellt einen formattierten Validierungsbericht."""
        if not proposal.validation_messages:
            return "✓ Validierung erfolgreich - keine Probleme"

        lines: list[str] = []
        lines.append(f"Validierungsbericht für: {proposal.invoice_name_long}")
        lines.append("")

        for msg in proposal.validation_messages:
            icon = "✗" if msg.level == "error" else "⚠" if msg.level == "warning" else "ℹ"
            lines.append(f"{icon} [{msg.level.upper():8}] {msg.field}: {msg.message}")

        if self.has_errors(proposal):
            lines.append("")
            lines.append("⚠ Diese Rechnung kann noch nicht exportiert werden (Fehler vorhanden)")

        return "\n".join(lines)
