import re
import unicodedata

from domain.invoice_models import CustomerMatchResult


class CustomerMatcherService:
    def match_exact(self, customer_raw: str, contacts: list[dict]) -> CustomerMatchResult:
        target = self._normalize(customer_raw)
        if not target:
            return CustomerMatchResult(state="nicht_zugeordnet")

        target_loose = self._normalize_loose(customer_raw)
        matches: list[dict] = []
        for contact in contacts or []:
            if self._normalize(self._extract_name(contact)) == target:
                matches.append(contact)

        if not matches and target_loose:
            for contact in contacts or []:
                if self._normalize_loose(self._extract_name(contact)) == target_loose:
                    matches.append(contact)

        if not matches and target_loose:
            fuzzy_matches = []
            target_tokens = self._tokenize(target_loose)
            for contact in contacts or []:
                candidate_name = self._extract_name(contact)
                candidate_loose = self._normalize_loose(candidate_name)
                if not candidate_loose:
                    continue

                candidate_tokens = self._tokenize(candidate_loose)
                if not target_tokens or not candidate_tokens:
                    continue

                # Fuzzy-Regel: wesentliche Namensanteile überlappen stark.
                overlap = len(target_tokens & candidate_tokens)
                min_tokens = min(len(target_tokens), len(candidate_tokens))
                if overlap >= max(1, min_tokens - 1):
                    fuzzy_matches.append(contact)

            matches = fuzzy_matches

        if not matches:
            return CustomerMatchResult(state="nicht_gefunden")

        if len(matches) > 1:
            return CustomerMatchResult(state="mehrdeutig", customer_name=customer_raw.strip())

        match = matches[0]
        return CustomerMatchResult(
            state="eindeutig",
            customer_name=self._extract_name(match),
            customer_number=self._extract_customer_number(match),
        )

    def _extract_name(self, contact: dict) -> str:
        for key in ["Firmenname", "Name", "name", "companyName", "company_name"]:
            value = str((contact or {}).get(key, "")).strip()
            if value:
                return value
        return ""

    def _extract_customer_number(self, contact: dict) -> str:
        for key in ["Kundennummer", "customerNumber", "customer_number", "Debitorennummer"]:
            value = str((contact or {}).get(key, "")).strip()
            if value:
                return value
        return ""

    def _normalize(self, value: str) -> str:
        return " ".join(str(value or "").strip().lower().split())

    def _normalize_loose(self, value: str) -> str:
        text = str(value or "").strip().lower()
        text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
        text = re.sub(r"[^a-z0-9]+", " ", text)
        tokens = [t for t in text.split() if t and t not in {
            "gmbh", "mbh", "ag", "kg", "co", "ug", "haftungsbeschrankt", "und", "the", "ltd", "llc",
        }]
        return " ".join(tokens)

    def _tokenize(self, value: str) -> set[str]:
        return {t for t in str(value or "").split() if t}