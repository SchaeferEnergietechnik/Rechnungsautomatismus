class BlockClassificationService:
    def classify(self, block: dict) -> tuple[str, str]:
        status_text = str(block.get("status_oder_kunde", "")).strip()
        kunde_text = str(block.get("kunde", "")).strip()
        projekt_text = str(block.get("projekt", "")).strip()
        auftrag_text = str(block.get("auftrag", "")).strip()
        bemerkung_text = str(block.get("bemerkungen", "")).strip()

        text_values = " ".join(
            [
                status_text,
                kunde_text,
                projekt_text,
                auftrag_text,
                bemerkung_text,
            ]
        ).strip()
        text_values_lower = text_values.lower()

        if not text_values_lower:
            return "hinweis", "Kein relevanter Text gefunden"

        if "frei" in text_values_lower:
            has_assignment = bool(kunde_text or projekt_text or auftrag_text or bemerkung_text)
            if has_assignment and status_text.lower() == "frei":
                return "prueffall", "Status ist 'frei', aber zusätzliche Einsatzdaten sind vorhanden"
            return "frei", "Status 'frei' erkannt"

        if "krank" in text_values_lower:
            has_assignment = bool(kunde_text or projekt_text or auftrag_text or bemerkung_text)
            if has_assignment and status_text.lower() == "krank":
                return "prueffall", "Status ist 'krank', aber zusätzliche Einsatzdaten sind vorhanden"
            return "krank", "Status 'krank' erkannt"

        if "urlaub" in text_values_lower:
            return "urlaub", "Status/Eintrag 'urlaub' erkannt"

        if "ferien" in text_values_lower:
            return "urlaub", "Status/Eintrag 'ferien' erkannt"

        if "feiertag" in text_values_lower:
            return "feiertag", "Status/Eintrag 'feiertag' erkannt"

        intern_keywords = [
            "intern",
            "schulung",
            "abholung kfz",
            "schaltberechtigung",
            "fernsupport intern"
        ]
        for keyword in intern_keywords:
            if keyword in text_values_lower:
                return "intern", f"Interner Eintrag wegen Schlüsselwort '{keyword}' erkannt"

        prueffall_keywords = [
            "abgesagt",
            "ausgefallen",
            "wartezeit",
            "nur cmufd",
            "klären",
            "unklar",
            "offene fragen",
        ]
        for keyword in prueffall_keywords:
            if keyword in text_values_lower:
                return "prueffall", f"Prüffall wegen Schlüsselwort '{keyword}' erkannt"

        has_customer = bool(kunde_text)
        has_project = bool(projekt_text)
        has_assignment_text = bool(auftrag_text or bemerkung_text)

        if has_customer and has_project:
            return "einsatz", "Einsatz erkannt: Kunde und Projekt vorhanden"

        if has_customer and has_assignment_text:
            return "einsatz", "Einsatz erkannt: Kunde und Auftrags-/Bemerkungstext vorhanden"

        if has_project and has_assignment_text:
            return "einsatz", "Einsatz erkannt: Projekt und Auftrags-/Bemerkungstext vorhanden"

        if has_customer:
            return "einsatz", "Einsatz erkannt: Kunde vorhanden"

        if has_project:
            return "einsatz", "Einsatz erkannt: Projekt vorhanden"

        if has_assignment_text:
            return "einsatz", "Einsatz erkannt: Auftrags-/Bemerkungstext vorhanden"

        return "hinweis", "Text vorhanden, aber kein klarer Einsatz erkennbar"
