from domain.invoice_models import CustomerMatchResult


class CustomerMatcherService:
    def match_exact(self, customer_raw: str, contacts: list[dict]) -> CustomerMatchResult:
        target = self._normalize(customer_raw)
        if not target:
            return CustomerMatchResult(state="nicht_zugeordnet")

        matches: list[dict] = []
        for contact in contacts or []:
            if self._normalize(self._extract_name(contact)) == target:
                matches.append(contact)

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