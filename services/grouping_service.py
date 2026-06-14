from datetime import datetime


class GroupingService:
    def group_candidates(self, candidates: list[dict]) -> list[dict]:
        partitions: dict[tuple[str, str], list[dict]] = {}

        for candidate in candidates:
            key = (
                str(candidate.get("kunde_roh", "")).strip().lower(),
                str(candidate.get("projekt_roh", "")).strip().lower(),
            )
            partitions.setdefault(key, []).append(candidate)

        result: list[dict] = []

        for partition in partitions.values():
            sorted_partition = sorted(
                partition,
                key=lambda c: (
                    self._parse_date(str(c.get("datum", "")).strip()) or datetime.max,
                    str(c.get("datum", "")).strip(),
                ),
            )
            result.extend(self._group_partition(sorted_partition))

        result.sort(
            key=lambda g: (
                self._parse_date(str(g.get("datum", "")).strip()) or datetime.max,
                str(g.get("kunde_roh", "")).lower(),
                str(g.get("projekt_roh", "")).lower(),
            )
        )
        return result

    def _group_partition(self, candidates: list[dict]) -> list[dict]:
        groups: list[dict] = []
        current_group: dict | None = None
        current_date: datetime | None = None
        current_classification: str = ""

        for candidate in candidates:
            candidate_date = self._parse_date(str(candidate.get("datum", "")).strip())
            candidate_classification = str(candidate.get("klassifikation", "")).strip().lower()

            if current_group is None:
                current_group = self._new_group(candidate)
                current_date = candidate_date
                current_classification = candidate_classification
                continue

            should_split = self._should_split_group(
                current_date=current_date,
                candidate_date=candidate_date,
                current_classification=current_classification,
                candidate_classification=candidate_classification,
            )

            if should_split:
                groups.append(self._finalize_group(current_group))
                current_group = self._new_group(candidate)
            else:
                self._append_candidate(current_group, candidate)

            current_date = candidate_date
            current_classification = candidate_classification

        if current_group is not None:
            groups.append(self._finalize_group(current_group))

        return groups

    def _should_split_group(
        self,
        current_date: datetime | None,
        candidate_date: datetime | None,
        current_classification: str,
        candidate_classification: str,
    ) -> bool:
        if candidate_classification != current_classification:
            return True

        if current_date is None or candidate_date is None:
            return True

        day_diff = (candidate_date.date() - current_date.date()).days
        if day_diff < 0:
            return True

        return day_diff > 1

    def _new_group(self, candidate: dict) -> dict:
        group = {
            "datum": str(candidate.get("datum", "")).strip(),
            "zeitraum_von": str(candidate.get("datum", "")).strip(),
            "zeitraum_bis": str(candidate.get("datum", "")).strip(),
            "kw": str(candidate.get("kw", "")).strip(),
            "kunde_roh": str(candidate.get("kunde_roh", "")).strip(),
            "projekt_roh": str(candidate.get("projekt_roh", "")).strip(),
            "adresse_roh": str(candidate.get("adresse_roh", "")).strip(),
            "ansprechpartner_roh": str(candidate.get("ansprechpartner_roh", "")).strip(),
            "auftrag_roh": str(candidate.get("auftrag_roh", "")).strip(),
            "bemerkungen_roh": str(candidate.get("bemerkungen_roh", "")).strip(),
            "re_roh_set": set(),
            "mitarbeiter_liste": [],
            "eintraege": [],
            "klassifikationen": set(),
            "klassifikationsgruende": [],
            "manueller_status": "offen",
        }
        self._append_candidate(group, candidate)
        return group

    def _append_candidate(self, group: dict, candidate: dict) -> None:
        group["zeitraum_bis"] = str(candidate.get("datum", "")).strip() or group.get("zeitraum_bis", "")

        if not group.get("adresse_roh"):
            group["adresse_roh"] = str(candidate.get("adresse_roh", "")).strip()
        if not group.get("ansprechpartner_roh"):
            group["ansprechpartner_roh"] = str(candidate.get("ansprechpartner_roh", "")).strip()
        if not group.get("auftrag_roh"):
            group["auftrag_roh"] = str(candidate.get("auftrag_roh", "")).strip()
        if not group.get("bemerkungen_roh"):
            group["bemerkungen_roh"] = str(candidate.get("bemerkungen_roh", "")).strip()

        group["eintraege"].append(candidate)

        employee = str(candidate.get("mitarbeiter", "")).strip()
        if employee:
            group["mitarbeiter_liste"].append(employee)

        re_value = str(candidate.get("re_roh", "")).strip()
        if re_value:
            group["re_roh_set"].add(re_value)

        klassifikation = str(candidate.get("klassifikation", "")).strip()
        if klassifikation:
            group["klassifikationen"].add(klassifikation)

        grund = str(candidate.get("klassifikationsgrund", "")).strip()
        if grund:
            group["klassifikationsgruende"].append(grund)

    def _finalize_group(self, group: dict) -> dict:
        if not group.get("eintraege"):
            return group

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

        return group

    def _parse_date(self, text: str) -> datetime | None:
        value = str(text or "").strip()
        if not value:
            return None

        for fmt in [
            "%d.%m.%Y",
            "%Y-%m-%d",
            "%Y-%m-%d %H:%M:%S",
            "%d.%m.%Y %H:%M:%S",
            "%Y-%m-%d %H:%M:%S.%f",
        ]:
            try:
                return datetime.strptime(value, fmt)
            except Exception:
                pass

        try:
            return datetime.fromisoformat(value)
        except Exception:
            return None
