class GroupingService:
    def group_candidates(self, candidates: list[dict]) -> list[dict]:
        grouped: dict = {}

        for candidate in candidates:
            key = (
                candidate.get("datum", "").strip(),
                candidate.get("kunde_roh", "").strip().lower(),
                candidate.get("projekt_roh", "").strip().lower(),
            )

            if key not in grouped:
                grouped[key] = {
                    "datum": candidate.get("datum", "").strip(),
                    "kw": candidate.get("kw", "").strip(),
                    "kunde_roh": candidate.get("kunde_roh", "").strip(),
                    "projekt_roh": candidate.get("projekt_roh", "").strip(),
                    "adresse_roh": candidate.get("adresse_roh", "").strip(),
                    "ansprechpartner_roh": candidate.get("ansprechpartner_roh", "").strip(),
                    "auftrag_roh": candidate.get("auftrag_roh", "").strip(),
                    "bemerkungen_roh": candidate.get("bemerkungen_roh", "").strip(),
                    "re_roh_set": set(),
                    "mitarbeiter_liste": [],
                    "eintraege": [],
                    "klassifikationen": set(),
                    "klassifikationsgruende": [],
                    "manueller_status": "offen",
                }

            grouped[key]["eintraege"].append(candidate)
            grouped[key]["mitarbeiter_liste"].append(candidate.get("mitarbeiter", "").strip())

            re_value = candidate.get("re_roh", "").strip()
            if re_value:
                grouped[key]["re_roh_set"].add(re_value)

            klassifikation = candidate.get("klassifikation", "").strip()
            if klassifikation:
                grouped[key]["klassifikationen"].add(klassifikation)

            grund = candidate.get("klassifikationsgrund", "").strip()
            if grund:
                grouped[key]["klassifikationsgruende"].append(grund)

        result: list[dict] = []

        for group in grouped.values():
            group["mitarbeiter_liste"] = sorted(set(m for m in group["mitarbeiter_liste"] if m))
            group["re_roh_liste"] = sorted(group["re_roh_set"])
            del group["re_roh_set"]

            klassifikationen = sorted(group["klassifikationen"])
            del group["klassifikationen"]

            if "prueffall" in klassifikationen:
                group["gruppenstatus"] = "prueffall"
            elif "einsatz" in klassifikationen:
                group["gruppenstatus"] = "einsatz"
            else:
                group["gruppenstatus"] = "unbekannt"

            result.append(group)

        result.sort(key=lambda g: (g.get("datum", ""), g.get("kunde_roh", ""), g.get("projekt_roh", "")))
        return result
