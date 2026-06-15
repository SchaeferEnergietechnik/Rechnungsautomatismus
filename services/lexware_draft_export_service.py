import json
import os
import re
from datetime import datetime, timedelta
from urllib import parse
from urllib import error, request

from domain.invoice_models import InvoiceProposal
from services.invoice_position_service import InvoicePositionService


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
        self.templates_endpoint = os.getenv("LEXWARE_TEMPLATES_ENDPOINT", "/v1/text-modules").strip() or "/v1/text-modules"
        self.customers_endpoint = os.getenv("LEXWARE_CUSTOMERS_ENDPOINT", "/v1/contacts").strip() or "/v1/contacts"
        self.default_net_amount = self._safe_float(os.getenv("LEXWARE_DEFAULT_NET_AMOUNT", "1.0"), 1.0)
        self.default_tax_rate = self._safe_float(os.getenv("LEXWARE_DEFAULT_TAX_RATE", "19.0"), 19.0)
        self.default_payment_term_days = self._safe_int(os.getenv("LEXWARE_PAYMENT_TERM_DAYS", "14"), 14)
        self.position_service = InvoicePositionService()

        if not self.token_url and self.base_url:
            self.token_url = f"{self.base_url.rstrip('/')}/oauth/token"

    def is_configured(self) -> bool:
        has_direct_access = bool(self.access_token)
        has_refresh_flow = bool(self.refresh_token and self.client_id and self.client_secret and self.token_url)
        return bool(self.base_url and (has_direct_access or has_refresh_flow))

    def export_group_as_draft(
        self,
        group: dict,
        company_id: str = "",
        title: str = "",
        introduction: str = "",
        remark: str = "",
        payment_term_days: int | None = None,
        payment_term_label: str = "",
        update_existing: bool = False,
        export_reference: str = "",
        voucher_type: str = "",
        finalize: bool = False,
    ) -> dict:
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

        payload_variants = self._build_payload_variants(
            group,
            title=title,
            introduction=introduction,
            remark=remark,
            payment_term_days=payment_term_days,
            payment_term_label=payment_term_label,
            voucher_type=voucher_type,
        )
        payload = payload_variants[0]
        endpoint_override = self._endpoint_for_voucher_type(voucher_type)
        if update_existing and str(export_reference or "").strip():
            url = self._build_update_url(str(export_reference or "").strip(), endpoint_override=endpoint_override)
            first_try = self._update_draft(url, payload, company_id=company_id)
        else:
            url = self._build_url(endpoint_override=endpoint_override, finalize=bool(finalize))
            first_try = self._post_draft(url, payload, company_id=company_id)
        if first_try.get("success"):
            return first_try

        if self._is_lineitems_validation_error(first_try) and not update_existing:
            for variant_payload in payload_variants[1:]:
                retry_try = self._post_draft(url, variant_payload, company_id=company_id)
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

        if update_existing and str(export_reference or "").strip():
            second_try = self._update_draft(url, payload, company_id=company_id)
        else:
            second_try = self._post_draft(url, payload, company_id=company_id)
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

    def _post_draft(self, url: str, payload: dict, company_id: str = "") -> dict:
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        effective_company_id = str(company_id or self.company_id).strip()
        if effective_company_id:
            headers["X-LX-Company-ID"] = effective_company_id

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

    def _update_draft(self, url: str, payload: dict, company_id: str = "") -> dict:
        put_try = self._send_draft_with_method("PUT", url, payload, company_id=company_id)
        if put_try.get("success"):
            return put_try

        # Fallback: einige APIs akzeptieren PATCH statt PUT.
        if put_try.get("status_code") in {400, 404, 405}:
            patch_try = self._send_draft_with_method("PATCH", url, payload, company_id=company_id)
            if patch_try.get("success"):
                return patch_try
        return put_try

    def _send_draft_with_method(self, method: str, url: str, payload: dict, company_id: str = "") -> dict:
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        effective_company_id = str(company_id or self.company_id).strip()
        if effective_company_id:
            headers["X-LX-Company-ID"] = effective_company_id

        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = request.Request(url, data=body, headers=headers, method=str(method or "POST").upper())

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

    def fetch_customers(self, query: str = "", company_id: str = "") -> dict:
        if not self.is_configured():
            return {
                "success": False,
                "status_code": None,
                "error": "Lexware nicht konfiguriert (BASE_URL + ACCESS_TOKEN oder Refresh-Flow fehlen).",
                "response": None,
                "customers": [],
            }

        if not self.access_token:
            refresh_result = self._refresh_access_token()
            if not refresh_result.get("success"):
                return {
                    "success": False,
                    "status_code": refresh_result.get("status_code"),
                    "error": f"Token-Refresh fehlgeschlagen: {refresh_result.get('error')}",
                    "response": refresh_result.get("response"),
                    "customers": [],
                }

        base_url = self._build_url_for_endpoint(self.customers_endpoint)
        query_text = str(query or "").strip()

        page = 0
        page_size = 200
        max_pages = 30
        collected_items: list[dict] = []
        seen_page_signatures: set[str] = set()
        last_result: dict | None = None

        while page < max_pages:
            params = {"page": page, "size": page_size}
            if query_text:
                params["q"] = query_text

            url = f"{base_url}?{parse.urlencode(params)}"
            result = self._get_json(url, company_id=company_id)
            last_result = result
            if not result.get("success"):
                return {
                    **result,
                    "customers": [],
                }

            response = result.get("response")
            items = [item for item in self._extract_list_payload(response) if isinstance(item, dict)]
            collected_items.extend(items)

            signature = "|".join(
                str(item.get("id") or item.get("uuid") or item.get("contactId") or item.get("name") or "")
                for item in items
            )
            if signature in seen_page_signatures:
                break
            seen_page_signatures.add(signature)

            if not self._has_next_page(response, page, len(items), page_size):
                break

            page += 1

        effective_result = last_result or {
            "success": True,
            "status_code": 200,
            "error": "",
            "response": None,
        }

        customers = [self._normalize_customer(item) for item in collected_items if isinstance(item, dict)]
        customers = [x for x in customers if x.get("name")]
        return {
            **effective_result,
            "customers": customers,
        }

    def _has_next_page(self, response, current_page: int, item_count: int, page_size: int) -> bool:
        if isinstance(response, dict):
            total_pages = response.get("totalPages")
            try:
                if total_pages is not None:
                    return (current_page + 1) < int(total_pages)
            except Exception:
                pass

            for flag_key in ["hasNext", "has_next", "nextPage", "next"]:
                flag = response.get(flag_key)
                if isinstance(flag, bool):
                    return flag
                if isinstance(flag, (int, float)):
                    return bool(flag)

            last_flag = response.get("last")
            if isinstance(last_flag, bool):
                return not last_flag

        # Fallback: solange Seite voll ist, könnte es noch Folgeseiten geben.
        return item_count >= max(int(page_size), 1)

    def fetch_text_templates(
        self,
        voucher_type: str = "",
        customer_number: str = "",
        customer_name: str = "",
        company_id: str = "",
    ) -> dict:
        if not self.is_configured():
            return {
                "success": False,
                "status_code": None,
                "error": "Lexware nicht konfiguriert (BASE_URL + ACCESS_TOKEN oder Refresh-Flow fehlen).",
                "response": None,
                "templates": [],
            }

        if not self.access_token:
            refresh_result = self._refresh_access_token()
            if not refresh_result.get("success"):
                return {
                    "success": False,
                    "status_code": refresh_result.get("status_code"),
                    "error": f"Token-Refresh fehlgeschlagen: {refresh_result.get('error')}",
                    "response": refresh_result.get("response"),
                    "templates": [],
                }

        normalized_voucher_type = str(voucher_type or "").strip().lower()

        def _load_templates(use_voucher_filter: bool) -> dict:
            base_url = self._build_url_for_endpoint(self.templates_endpoint)
            page = 0
            page_size = 200
            max_pages = 30
            collected_items: list[dict] = []
            seen_page_signatures: set[str] = set()
            last_result: dict | None = None

            while page < max_pages:
                params = {"page": page, "size": page_size}
                if use_voucher_filter and normalized_voucher_type:
                    params["voucherType"] = normalized_voucher_type

                url = f"{base_url}?{parse.urlencode(params)}"
                result = self._get_json(url, company_id=company_id)
                last_result = result
                if not result.get("success"):
                    return {
                        **result,
                        "templates": [],
                    }

                response = result.get("response")
                items = [item for item in self._extract_list_payload(response) if isinstance(item, dict)]
                collected_items.extend(items)

                signature = "|".join(
                    str(item.get("id") or item.get("uuid") or item.get("name") or item.get("title") or "")
                    for item in items
                )
                if signature in seen_page_signatures:
                    break
                seen_page_signatures.add(signature)

                if not self._has_next_page(response, page, len(items), page_size):
                    break

                page += 1

            effective_result = last_result or {
                "success": True,
                "status_code": 200,
                "error": "",
                "response": None,
            }

            templates = [
                self._normalize_template(item)
                for item in collected_items
                if isinstance(item, dict)
            ]
            templates = [x for x in templates if x.get("name")]
            return {
                **effective_result,
                "templates": templates,
            }

        loaded = _load_templates(use_voucher_filter=True)
        templates = loaded.get("templates", [])

        # Fallback: einige Accounts liefern ohne voucherType-Filter, aber leer mit Filter.
        if normalized_voucher_type and not templates and loaded.get("success"):
            loaded = _load_templates(use_voucher_filter=False)
            templates = loaded.get("templates", [])

        if not loaded.get("success"):
            return {
                **loaded,
                "templates": [],
            }

        customer_number_norm = str(customer_number or "").strip().lower()
        customer_name_norm = str(customer_name or "").strip().lower()
        if customer_number_norm:
            templates = [
                x for x in templates
                if not x.get("customer_number")
                or customer_number_norm in str(x.get("customer_number", "")).strip().lower()
            ]
        if customer_name_norm:
            templates = [
                x for x in templates
                if not x.get("customer_name")
                or customer_name_norm in str(x.get("customer_name", "")).strip().lower()
            ]

        if normalized_voucher_type:
            templates = [
                x for x in templates
                if not x.get("voucher_type")
                or normalized_voucher_type in str(x.get("voucher_type", "")).strip().lower()
            ]

        return {
            **loaded,
            "templates": templates,
        }

    def _get_json(self, url: str, company_id: str = "", _retried: bool = False) -> dict:
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
        }
        effective_company_id = str(company_id or self.company_id).strip()
        if effective_company_id:
            headers["X-LX-Company-ID"] = effective_company_id

        req = request.Request(url, headers=headers, method="GET")
        try:
            with request.urlopen(req, timeout=30) as resp:
                text = resp.read().decode("utf-8", errors="replace")
                parsed = self._try_parse_json(text)
                return {
                    "success": 200 <= resp.status < 300,
                    "status_code": resp.status,
                    "error": "",
                    "response": parsed if parsed is not None else text,
                }
        except error.HTTPError as exc:
            text = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
            parsed = self._try_parse_json(text)

            if exc.code == 401 and not _retried:
                refresh_result = self._refresh_access_token()
                if refresh_result.get("success"):
                    return self._get_json(url, company_id=company_id, _retried=True)

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

    def _build_url(self, endpoint_override: str = "", finalize: bool = False) -> str:
        endpoint = str(endpoint_override or self.draft_endpoint or "").strip()
        if endpoint.startswith("http://") or endpoint.startswith("https://"):
            return self._with_finalize_query(endpoint, finalize)
        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        return self._with_finalize_query(url, finalize)

    def _build_url_for_endpoint(self, endpoint: str) -> str:
        text = str(endpoint or "").strip()
        if text.startswith("http://") or text.startswith("https://"):
            return text
        return f"{self.base_url.rstrip('/')}/{text.lstrip('/')}"

    def _build_update_url(self, export_reference: str, endpoint_override: str = "") -> str:
        reference = str(export_reference or "").strip()
        if not reference:
            return self._build_url(endpoint_override=endpoint_override)
        if reference.startswith("http://") or reference.startswith("https://"):
            return reference
        if reference.startswith("/"):
            return self._build_url_for_endpoint(reference)
        return f"{self._build_url(endpoint_override=endpoint_override).rstrip('/')}/{parse.quote(reference, safe='')}"

    def _with_finalize_query(self, url: str, finalize: bool) -> str:
        if not finalize:
            return str(url or "").strip()

        text = str(url or "").strip()
        if not text:
            return text

        separator = "&" if "?" in text else "?"
        return f"{text}{separator}finalize=true"

    def _endpoint_for_voucher_type(self, voucher_type: str) -> str:
        normalized = str(voucher_type or "").strip().lower()
        if normalized == "invoice":
            return "/v1/invoices"
        if normalized == "quotation":
            return "/v1/quotations"
        return str(self.draft_endpoint or "").strip()

    def _extract_list_payload(self, payload) -> list:
        if isinstance(payload, list):
            return payload
        if not isinstance(payload, dict):
            return []

        for key in ["content", "items", "data", "results", "templates", "contacts", "textModules", "modules"]:
            value = payload.get(key)
            if isinstance(value, list):
                return value
        return []

    def _normalize_customer(self, item: dict) -> dict:
        customer_id = str(item.get("id") or item.get("uuid") or item.get("contactId") or "").strip()
        customer_number = str(item.get("customerNumber") or item.get("number") or item.get("contactNumber") or "").strip()

        company = item.get("company") if isinstance(item.get("company"), dict) else {}
        person = item.get("person") if isinstance(item.get("person"), dict) else {}
        display_name = str(
            item.get("name")
            or item.get("displayName")
            or company.get("name")
            or " ".join(
                x for x in [
                    str(person.get("firstName", "") or "").strip(),
                    str(person.get("lastName", "") or "").strip(),
                ] if x
            )
            or ""
        ).strip()

        city = ""
        addresses = item.get("addresses") if isinstance(item.get("addresses"), list) else []
        if addresses:
            first_address = addresses[0] if isinstance(addresses[0], dict) else {}
            city = str(first_address.get("city") or first_address.get("locality") or "").strip()
        if not city and isinstance(company, dict):
            company_address = company.get("address") if isinstance(company.get("address"), dict) else {}
            city = str(company_address.get("city") or company_address.get("locality") or "").strip()
        if not city:
            city = str(item.get("city") or item.get("ort") or item.get("Ort 1") or "").strip()

        return {
            "id": customer_id,
            "customer_number": customer_number,
            "name": display_name,
            "city": city,
            "raw": item,
        }

    def _normalize_template(self, item: dict) -> dict:
        template_id = str(item.get("id") or item.get("uuid") or "").strip()
        name = str(item.get("name") or item.get("title") or item.get("label") or "Vorlage").strip()

        module_type = str(item.get("moduleType") or item.get("textType") or item.get("kind") or "").strip().lower()
        text_value = self._extract_text_value(item.get("text")) or self._extract_text_value(item.get("content")) or self._extract_text_value(item.get("body"))

        introduction = (
            self._extract_text_value(item.get("introduction"))
            or self._extract_text_value(item.get("intro"))
            or self._extract_text_value(item.get("introductionText"))
            or self._extract_text_value(item.get("header"))
        )
        remark = (
            self._extract_text_value(item.get("remark"))
            or self._extract_text_value(item.get("footer"))
            or self._extract_text_value(item.get("outro"))
            or self._extract_text_value(item.get("remarkText"))
        )

        if text_value and not introduction and not remark:
            if "intro" in module_type or "header" in module_type or "einleitung" in module_type:
                introduction = text_value
            elif "remark" in module_type or "footer" in module_type or "nachbemerk" in module_type:
                remark = text_value
            else:
                introduction = text_value

        customer_number = str(
            item.get("customerNumber")
            or item.get("contactNumber")
            or item.get("customerNo")
            or ""
        ).strip()
        customer_name = str(
            item.get("customerName")
            or item.get("contactName")
            or item.get("customer")
            or ""
        ).strip()
        voucher_type = str(item.get("voucherType") or item.get("type") or item.get("category") or "").strip()

        return {
            "id": template_id,
            "name": name,
            "introduction": introduction,
            "remark": remark,
            "customer_number": customer_number,
            "customer_name": customer_name,
            "voucher_type": voucher_type,
            "raw": item,
        }

    def _extract_text_value(self, value) -> str:
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, dict):
            for key in ["text", "content", "value", "body", "message"]:
                nested = self._extract_text_value(value.get(key))
                if nested:
                    return nested
            return ""
        if isinstance(value, list):
            parts = [self._extract_text_value(item) for item in value]
            parts = [p for p in parts if p]
            return "\n".join(parts).strip()
        return ""

    def _build_payload(
        self,
        group: dict,
        title: str = "",
        introduction: str = "",
        remark: str = "",
        payment_term_days: int | None = None,
        payment_term_label: str = "",
        voucher_type: str = "",
    ) -> dict:
        customer_name = str(group.get("customer_match_name", "") or group.get("kunde_roh", "")).strip() or "Unbekannter Kunde"
        project_name = str(group.get("projekt_roh", "")).strip() or "Leistung"
        voucher_date = self._as_lexware_datetime(group.get("datum", ""))
        effective_payment_term_days = self.default_payment_term_days if payment_term_days is None else max(int(payment_term_days), 0)
        effective_payment_term_label = str(payment_term_label or "").strip() or f"{effective_payment_term_days} Tage netto"
        
        is_quotation = self._is_quotation_endpoint(self._endpoint_for_voucher_type(voucher_type))
        base_title = "Angebot" if is_quotation else "Rechnung"
        raw_title = str(title or "").strip()
        is_auto_title = bool(re.match(r"^(angebot|rechnung)\s*-", raw_title, flags=re.IGNORECASE))
        if not raw_title or raw_title.lower() in {"angebot", "rechnung"} or is_auto_title:
            effective_title = f"{base_title} - {project_name}"
        else:
            effective_title = raw_title
        effective_introduction = str(introduction or "").strip() or f"Automatisch erzeugter Entwurf für {project_name}"
        effective_remark = str(remark or "").strip() or "Erzeugt durch Rechnungsautomatismus"

        description_parts = [
            f"Projekt: {project_name}",
        ]
        remarks = str(group.get("bemerkungen_roh", "")).strip()
        if remarks:
            description_parts.append(f"Bemerkung: {remarks}")

        line_items = self._build_line_items_from_group(group, project_name, description_parts)
        customer_street = str(group.get("customer_match_street", "") or "").strip()
        customer_zip = str(group.get("customer_match_zip", "") or "").strip()
        customer_city = str(group.get("customer_match_city", "") or "").strip()
        customer_country = str(group.get("customer_match_country", "") or "DE").strip() or "DE"

        payload = {
            "voucherStatus": "draft",
            "voucherDate": voucher_date,
            "address": {
                "name": customer_name,
                "street": customer_street,
                "city": customer_city,
                "zip": customer_zip,
                "countryCode": customer_country,
            },
            "lineItems": line_items,
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
            "title": effective_title,
            "introduction": effective_introduction,
            "remark": effective_remark,
        }

        # Quotations require an expirationDate in Lexware.
        if is_quotation:
            payload["expirationDate"] = self._add_days_to_lexware_datetime(
                voucher_date,
                effective_payment_term_days,
            )

        payload["paymentConditions"]["paymentTermDuration"] = effective_payment_term_days
        payload["paymentConditions"]["paymentTermLabel"] = effective_payment_term_label

        return payload

    def _build_line_items_from_group(self, group: dict, project_name: str, description_parts: list[str]) -> list[dict]:
        proposal = InvoiceProposal(
            source_group_key="preview",
            start_date=str(group.get("zeitraum_von") or group.get("datum") or ""),
            end_date=str(group.get("zeitraum_bis") or group.get("datum") or ""),
            kw=str(group.get("kw", "") or ""),
            customer_raw=str(group.get("kunde_roh", "") or ""),
            project_raw=project_name,
        )
        self.position_service.enrich_proposal_with_positions(proposal, group)

        if not proposal.positions:
            return [self._build_line_item(project_name, description_parts)]

        line_items = []
        for position in proposal.positions:
            tax_rate = float(position.tax_rate or self.default_tax_rate)
            net = float(position.unit_price_net or self.default_net_amount)
            gross = round(net * (1 + (tax_rate / 100.0)), 2)

            base_description = str(getattr(position, "description", "") or "").strip()
            line_description_parts = [base_description] if base_description else [part for part in description_parts if part]

            line_items.append(
                {
                    "type": "custom",
                    "name": str(position.title or f"Rechnung {project_name}")[:120],
                    "description": " | ".join(line_description_parts),
                    "quantity": float(position.quantity or 1.0),
                    "unitName": str(position.unit or "Stk"),
                    "unitPrice": {
                        "currency": "EUR",
                        "netAmount": net,
                        "grossAmount": gross,
                        "taxRatePercentage": tax_rate,
                    },
                }
            )

        return line_items

    def _build_payload_variants(
        self,
        group: dict,
        title: str = "",
        introduction: str = "",
        remark: str = "",
        payment_term_days: int | None = None,
        payment_term_label: str = "",
        voucher_type: str = "",
    ) -> list[dict]:
        base_payload = self._build_payload(
            group,
            title=title,
            introduction=introduction,
            remark=remark,
            payment_term_days=payment_term_days,
            payment_term_label=payment_term_label,
            voucher_type=voucher_type,
        )

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

    def _is_quotation_endpoint(self, endpoint_override: str = "") -> bool:
        endpoint = str(endpoint_override or self.draft_endpoint or "").strip().lower()
        return "quotations" in endpoint

    def is_quotation_mode(self, voucher_type: str = "") -> bool:
        endpoint = self._endpoint_for_voucher_type(voucher_type)
        return self._is_quotation_endpoint(endpoint)

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
