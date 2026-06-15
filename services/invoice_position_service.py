"""Service zur Extraktion von Rechnungspositionen aus Einsatzgruppen."""
import re

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
        article_positions = self._build_positions_from_articles(group)
        if article_positions:
            self._apply_travel_costs(group, article_positions)
            proposal.positions = article_positions
            return

        positions = self.extract_positions_simple(group)

        selected_article = group.get("selected_article", {})
        if isinstance(selected_article, dict) and selected_article:
            article_name = str(selected_article.get("Bezeichnung", "") or "").strip()
            article_unit = str(selected_article.get("Einheit", "") or "").strip()
            article_price = self._parse_decimal(selected_article.get("VK (Netto)", ""))
            article_tax_rate = self._parse_tax_rate(selected_article.get("Steuerart", ""))

            for position in positions:
                if article_name:
                    position.title = f"{article_name} - {position.title}" if position.title else article_name
                if article_unit:
                    position.unit = article_unit
                if article_price is not None:
                    position.unit_price_net = article_price
                if article_tax_rate is not None:
                    position.tax_rate = article_tax_rate

            self._apply_travel_costs(group, positions)

        proposal.positions = positions

    def _build_positions_from_articles(self, group: dict) -> list[InvoicePosition]:
        articles = group.get("selected_articles", [])
        if not isinstance(articles, list) or not articles:
            single_article = group.get("selected_article", {})
            if isinstance(single_article, dict) and single_article:
                articles = [single_article]
            else:
                return []

        positions: list[InvoicePosition] = []
        for index, article in enumerate(articles, start=1):
            if not isinstance(article, dict):
                continue

            article_name = str(article.get("Bezeichnung", "") or "").strip() or f"Artikel {index}"
            article_number = str(article.get("Artikelnummer", "") or "").strip()
            article_unit = str(article.get("Einheit", "") or "").strip() or "Stk"
            article_price = self._parse_decimal(article.get("VK (Netto)", "")) or 0.0
            article_tax_rate = self._parse_tax_rate(article.get("Steuerart", "")) or 19.0
            article_description = str(article.get("Beschreibung", "") or "").strip()
            article_note = str(article.get("Notiz", "") or "").strip()

            description_parts = [part for part in [article_description, article_note] if part]
            merged_description = "\n".join(description_parts)

            title_parts = []
            if article_number:
                title_parts.append(article_number)
            title_parts.append(article_name)

            positions.append(
                InvoicePosition(
                    title=" - ".join(title_parts),
                    description=merged_description,
                    quantity=1.0,
                    unit=article_unit,
                    unit_price_net=article_price,
                    tax_rate=article_tax_rate,
                )
            )

        self._apply_multi_day_allowance_assignment(group, positions)

        return positions

    def _apply_multi_day_allowance_assignment(self, group: dict, positions: list[InvoicePosition]) -> None:
        if not positions:
            return

        start_date = str(group.get("zeitraum_von", "") or group.get("datum", "") or "").strip()
        end_date = str(group.get("zeitraum_bis", "") or group.get("datum", "") or "").strip()
        if not start_date or not end_date or start_date == end_date:
            return

        rule = str(group.get("multi_day_allowance_assignment_rule", "tag_1") or "tag_1").strip().lower()
        if rule not in {"tag_1", "tag_2"}:
            rule = "tag_1"

        target_day = start_date if rule == "tag_1" else end_date
        day_label = "Tag 1" if rule == "tag_1" else "Tag 2"
        assignment_text = f"Mehrtagespauschale zugeordnet: {day_label} ({target_day})"

        for position in positions:
            title = str(getattr(position, "title", "") or "").strip().lower()
            if "mehrtages" not in title:
                continue

            existing_description = str(getattr(position, "description", "") or "").strip()
            if assignment_text in existing_description:
                continue

            position.description = (
                (existing_description + "\n" + assignment_text).strip()
                if existing_description
                else assignment_text
            )

    def _apply_travel_costs(self, group: dict, positions: list[InvoicePosition]) -> None:
        travel_amount = self._travel_amount(group)
        if travel_amount <= 0:
            return

        mode = str(group.get("travel_mode", "extra_article") or "extra_article").strip()
        if mode == "included_in_first_article" and positions:
            positions[0].unit_price_net = round(float(positions[0].unit_price_net or 0.0) + travel_amount, 2)
            travel_detail = self.travel_detail_text(group)
            if travel_detail:
                prefix = str(positions[0].description or "").strip()
                if travel_detail not in prefix:
                    positions[0].description = (prefix + "\n" + travel_detail).strip() if prefix else travel_detail
            return

        if mode == "included_in_first_article" and not positions:
            mode = "extra_article"

        if mode == "extra_article":
            travel_detail = self.travel_detail_text(group)
            positions.append(
                InvoicePosition(
                    title="Fahrtkosten",
                    description=travel_detail,
                    quantity=1.0,
                    unit="Pauschale",
                    unit_price_net=travel_amount,
                    tax_rate=19.0,
                )
            )

    def travel_detail_text(self, group: dict) -> str:
        travel_amount = self._travel_amount(group)
        if travel_amount <= 0:
            return ""

        hours = self._as_float(group.get("travel_hours", 0.0), 0.0)
        km = self._as_float(group.get("travel_km", 0.0), 0.0)
        km_display = int(round(km))
        
        segment_role = str(group.get("travel_segment_role", "") or "").strip().lower()
        segment_desc = ""
        if segment_role == "first_invoice_outbound":
            segment_desc = "Anfahrt"
        elif segment_role == "last_invoice_with_return":
            segment_desc = "Zwischenfahrt + Rückfahrt"
        elif segment_role == "middle_invoice":
            segment_desc = "Zwischenfahrt"
        else:
            segment_desc = "Hin- und Rückfahrt"
        
        route_segments = group.get("travel_route_segments", [])
        route_info = ""
        if isinstance(route_segments, list) and route_segments:
            cleaned_segments = [str(seg).strip() for seg in route_segments if str(seg).strip()]
            if cleaned_segments:
                route_info = f" ({' | '.join(cleaned_segments)})"
        
        return f"Fahrtkostenangaben: {hours:.2f} h, {km_display} km ({segment_desc}){route_info}"

    def _travel_amount(self, group: dict) -> float:
        hours = self._as_float(group.get("travel_hours", 0.0), 0.0)
        km = self._as_float(group.get("travel_km", 0.0), 0.0)
        hour_rate = self._as_float(group.get("travel_hour_rate", 150.0), 0.0)
        km_rate = self._as_float(group.get("travel_km_rate", 0.7), 0.0)
        return round((hours * hour_rate) + (km * km_rate), 2)

    def _as_float(self, value, fallback: float) -> float:
        if isinstance(value, (int, float)):
            return float(value)

        parsed = self._parse_decimal(value)
        if parsed is None:
            return fallback
        return float(parsed)

    def _parse_decimal(self, value) -> float | None:
        text = str(value or "").strip()
        if not text:
            return None

        text = text.replace(".", "").replace(",", ".")
        match = re.search(r"-?\d+(?:\.\d+)?", text)
        if not match:
            return None

        try:
            return float(match.group(0))
        except Exception:
            return None

    def _parse_tax_rate(self, value) -> float | None:
        text = str(value or "").strip()
        if not text:
            return None

        match = re.search(r"\d+(?:[\.,]\d+)?", text)
        if not match:
            return None

        try:
            return float(match.group(0).replace(",", "."))
        except Exception:
            return None
