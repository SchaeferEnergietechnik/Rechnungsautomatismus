import json
import os
from datetime import datetime, timedelta
from urllib import parse
from urllib import error, request


class LexwareDraftExportService:
    def __init__(self) -> None:
        self.base_url = os.getenv("LEXWARE_BASE_URL", "").strip()
        self.access_token = os.getenv("LEXWARE_ACCESS_TOKEN", "").strip()
        self.client_id = os.getenv("LEXWARE_CLIENT_ID", "").strip()
        self.client_secret = os.getenv("LEXWARE_CLIENT_SECRET", "").strip()
        self.refresh_token = os.getenv("LEXWARE_REFRESH_TOKEN", "").strip()
        self.company_id = os.getenv("LEXWARE_COMPANY_ID", "").strip()
        self.draft_endpoint = os.getenv("LEXWARE_DRAFT_ENDPOINT", "/v1/quotations").strip() or "/v1/quotations"
        self.token_url = os.getenv("LEXWARE_TOKEN_URL", "").strip()
        self.default_net_amount = self._safe_float(os.getenv("LEXWARE_DEFAULT_NET_AMOUNT", "1.0"), 1.0)
        self.default_tax_rate = self._safe_float(os.getenv("LEXWARE_DEFAULT_TAX_RATE", "19.0"), 19.0)
        self.default_payment_term_days = self._safe_int(os.getenv("LEXWARE_PAYMENT_TERM_DAYS", "14"), 14)

        if not self.token_url and self.base_url:
            self.token_url = f"{self.base_url.rstrip('/')}/oauth/token"

    def is_configured(self) -> bool:
        has_direct_access = bool(self.access_token)
        has_refresh_flow = bool(self.refresh_token and self.client_id and self.client_secret and self.token_url)
        return bool(self.base_url and (has_direct_access or has_refresh_flow))

    def export_group_as_draft(self, group: dict) -> dict:
        if not self.is_configured():
            return {
                "success": False,
                "status_code": None,
                "error": "Lexware nicht konfiguriert (BASE_URL + ACCESS_TOKEN oder Refresh-Flow fehlen).",
                "response": None,
                "payload": None,
            }

        if not self.access_token:
            refresh_result = self._refresh_access_token()
            if not refresh_result.get("success"):
                return {
                    "success": False,
                    "status_code": refresh_result.get("status_code"),
                    "error": f"Token-Refresh fehlgeschlagen: {refresh_result.get('error')}",
                    "response": refresh_result.get("response"),
                    "payload": None,
                }

        payload_variants = self._build_payload_variants(group)
        payload = payload_variants[0]
        url = self._build_url()
        first_try = self._post_draft(url, payload)
        if first_try.get("success"):
            return first_try

        if self._is_lineitems_validation_error(first_try):
            for variant_payload in payload_variants[1:]:
                retry_try = self._post_draft(url, variant_payload)
                if retry_try.get("success"):
                    return retry_try
            return first_try

        if first_try.get("status_code") != 401:
            return first_try

        refresh_result = self._refresh_access_token()
        if not refresh_result.get("success"):
            first_try["error"] = f"HTTP 401 + Token-Refresh fehlgeschlagen: {refresh_result.get('error')}"
            first_try["refresh_response"] = refresh_result.get("response")
            return first_try

        second_try = self._post_draft(url, payload)
        if not second_try.get("success"):
            second_try["error"] = f"{second_try.get('error')} (nach Token-Refresh)"
        return second_try

    def _is_lineitems_validation_error(self, result: dict) -> bool:
        if result.get("status_code") != 400:
            return False

        response = result.get("response")
        if isinstance(response, dict):
            message = str(response.get("message", ""))
        else:
            message = str(response or "")

        return "lineitems" in message.lower()

    def _post_draft(self, url: str, payload: dict) -> dict:
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.company_id:
            headers["X-LX-Company-ID"] = self.company_id

        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = request.Request(url, data=body, headers=headers, method="POST")

        try:
            with request.urlopen(req, timeout=30) as resp:
                text = resp.read().decode("utf-8", errors="replace")
                parsed = self._try_parse_json(text)
                return {
                    "success": 200 <= resp.status < 300,
                    "status_code": resp.status,
                    "error": "",
                    "response": parsed if parsed is not None else text,
                    "payload": payload,
                }
        except error.HTTPError as exc:
            text = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
            parsed = self._try_parse_json(text)
            return {
                "success": False,
                "status_code": exc.code,
                "error": f"HTTP {exc.code}",
                "response": parsed if parsed is not None else text,
                "payload": payload,
            }
        except Exception as exc:
            return {
                "success": False,
                "status_code": None,
                "error": str(exc),
                "response": None,
                "payload": payload,
            }

    def _refresh_access_token(self) -> dict:
        if not (self.token_url and self.client_id and self.client_secret and self.refresh_token):
            return {
                "success": False,
                "status_code": None,
                "error": "Refresh-Konfiguration unvollständig (TOKEN_URL/CLIENT_ID/CLIENT_SECRET/REFRESH_TOKEN).",
                "response": None,
            }

        form_data = {
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        encoded = parse.urlencode(form_data).encode("utf-8")

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        }
        req = request.Request(self.token_url, data=encoded, headers=headers, method="POST")

        try:
            with request.urlopen(req, timeout=30) as resp:
                text = resp.read().decode("utf-8", errors="replace")
                parsed = self._try_parse_json(text)
                if not isinstance(parsed, dict):
                    return {
                        "success": False,
                        "status_code": resp.status,
                        "error": "Token-Response ist kein JSON-Objekt.",
                        "response": text,
                    }

                new_access = str(parsed.get("access_token", "")).strip()
                if not new_access:
                    return {
                        "success": False,
                        "status_code": resp.status,
                        "error": "Kein access_token in Token-Response.",
                        "response": parsed,
                    }

                self.access_token = new_access

                new_refresh = str(parsed.get("refresh_token", "")).strip()
                if new_refresh:
                    self.refresh_token = new_refresh

                return {
                    "success": True,
                    "status_code": resp.status,
                    "error": "",
                    "response": parsed,
                }
        except error.HTTPError as exc:
            text = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
            parsed = self._try_parse_json(text)
            return {
                "success": False,
                "status_code": exc.code,
                "error": f"HTTP {exc.code}",
                "response": parsed if parsed is not None else text,
            }
        except Exception as exc:
            return {
                "success": False,
                "status_code": None,
                "error": str(exc),
                "response": None,
            }

    def _build_url(self) -> str:
        if self.draft_endpoint.startswith("http://") or self.draft_endpoint.startswith("https://"):
            return self.draft_endpoint
        return f"{self.base_url.rstrip('/')}/{self.draft_endpoint.lstrip('/')}"

    def _build_payload(self, group: dict) -> dict:
        customer_name = str(group.get("kunde_roh", "")).strip() or "Unbekannter Kunde"
        project_name = str(group.get("projekt_roh", "")).strip() or "Leistung"
        voucher_date = self._as_lexware_datetime(group.get("datum", ""))

        description_parts = [
            f"Projekt: {project_name}",
            f"Mitarbeiter: {', '.join(group.get('mitarbeiter_liste', []))}",
        ]
        remarks = str(group.get("bemerkungen_roh", "")).strip()
        if remarks:
            description_parts.append(f"Bemerkung: {remarks}")

        line_item = self._build_line_item(project_name, description_parts)

        payload = {
            "voucherStatus": "draft",
            "voucherDate": voucher_date,
            "address": {
                "name": customer_name,
                "street": str(group.get("adresse_roh", "")).strip(),
                "city": "",
                "zip": "",
                "countryCode": "DE",
            },
            "lineItems": [line_item],
            "totalPrice": {
                "currency": "EUR",
            },
            "taxConditions": {
                "taxType": "net",
            },
            "paymentConditions": {
                "paymentTermLabel": f"{self.default_payment_term_days} Tage netto",
                "paymentTermDuration": self.default_payment_term_days,
            },
            "shippingConditions": {
                "shippingDate": voucher_date,
                "shippingType": "service",
            },
            "title": "Angebot" if self._is_quotation_endpoint() else "Rechnung",
            "introduction": f"Automatisch erzeugter Entwurf für {project_name}",
            "remark": "Erzeugt durch Rechnungsautomatismus",
        }

        # Quotations require an expirationDate in Lexware.
        if self._is_quotation_endpoint():
            payload["expirationDate"] = self._add_days_to_lexware_datetime(
                voucher_date,
                self.default_payment_term_days,
            )

        return payload

    def _build_payload_variants(self, group: dict) -> list[dict]:
        base_payload = self._build_payload(group)

        nested_payload = dict(base_payload)
        nested_payload["lineItems"] = {
            "lineItems": list(base_payload.get("lineItems", [])),
        }

        return [base_payload, nested_payload]

    def _build_line_item(self, project_name: str, description_parts: list[str]) -> dict:
        net = self.default_net_amount
        tax_rate = self.default_tax_rate
        gross = round(net * (1 + (tax_rate / 100.0)), 2)

        return {
            "type": "custom",
            "name": f"Rechnung {project_name}"[:120],
            "description": " | ".join([part for part in description_parts if part]),
            "quantity": 1,
            "unitName": "Stk",
            "unitPrice": {
                "currency": "EUR",
                "netAmount": net,
                "grossAmount": gross,
                "taxRatePercentage": tax_rate,
            },
        }

    def _as_lexware_datetime(self, value: str) -> str:
        text = str(value or "").strip()
        base_dt = datetime.now().astimezone()

        if not text:
            return base_dt.isoformat(timespec="milliseconds")

        formats = [
            "%d.%m.%Y",
            "%Y-%m-%d",
            "%Y-%m-%d %H:%M:%S",
            "%d.%m.%Y %H:%M:%S",
            "%Y-%m-%d %H:%M:%S.%f",
        ]
        for fmt in formats:
            try:
                parsed = datetime.strptime(text, fmt)
                parsed = parsed.replace(tzinfo=base_dt.tzinfo)
                return parsed.isoformat(timespec="milliseconds")
            except Exception:
                pass

        # Fallback for values like 2026-04-07 00:00:00.000000 or other variants.
        try:
            parsed = datetime.fromisoformat(text)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=base_dt.tzinfo)
            return parsed.isoformat(timespec="milliseconds")
        except Exception:
            pass

        return base_dt.isoformat(timespec="milliseconds")

    def _is_quotation_endpoint(self) -> bool:
        endpoint = str(self.draft_endpoint or "").strip().lower()
        return "quotations" in endpoint

    def _add_days_to_lexware_datetime(self, value: str, days: int) -> str:
        base_dt = datetime.now().astimezone()
        try:
            parsed = datetime.fromisoformat(str(value or "").strip())
        except Exception:
            parsed = base_dt

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=base_dt.tzinfo)

        return (parsed + timedelta(days=max(days, 0))).isoformat(timespec="milliseconds")

    def _try_parse_json(self, value: str):
        if not value:
            return None
        try:
            return json.loads(value)
        except Exception:
            return None

    def _safe_float(self, value: str, fallback: float) -> float:
        try:
            return float(str(value).strip())
        except Exception:
            return fallback

    def _safe_int(self, value: str, fallback: int) -> int:
        try:
            return int(str(value).strip())
        except Exception:
            return fallback
