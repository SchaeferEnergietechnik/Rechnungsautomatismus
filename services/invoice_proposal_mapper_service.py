from domain.invoice_models import InvoiceProposal
from services.customer_matcher_service import CustomerMatcherService
from services.invoice_position_service import InvoicePositionService
from services.invoice_validation_service import InvoiceValidationService


class InvoiceProposalMapperService:
    def __init__(
        self,
        customer_matcher: CustomerMatcherService | None = None,
        position_service: InvoicePositionService | None = None,
        validation_service: InvoiceValidationService | None = None,
    ) -> None:
        self.customer_matcher = customer_matcher or CustomerMatcherService()
        self.position_service = position_service or InvoicePositionService()
        self.validation_service = validation_service or InvoiceValidationService()

    def map_group(
        self,
        group: dict,
        default_mandant_id: str = "",
        contacts: list[dict] | None = None,
    ) -> InvoiceProposal:
        group_mandant_id = str(group.get("mandant_id", "") or "").strip()
        effective_mandant_id = str(default_mandant_id or group_mandant_id).strip()

        start_date = str(group.get("zeitraum_von") or group.get("datum") or "").strip()
        end_date = str(group.get("zeitraum_bis") or group.get("datum") or "").strip()
        customer_raw = str(group.get("kunde_roh", "")).strip()
        project_raw = str(group.get("projekt_roh", "")).strip()

        invoice_name_long = self._build_invoice_name(project_raw, start_date, end_date)
        voucher_title = self._build_lexware_title(project_raw)

        proposal = InvoiceProposal(
            source_group_key=self._build_group_key(group),
            start_date=start_date,
            end_date=end_date,
            kw=str(group.get("kw", "")).strip(),
            customer_raw=customer_raw,
            project_raw=project_raw,
            employees=sorted(set(str(e).strip() for e in group.get("mitarbeiter_liste", []) if str(e).strip())),
            mandant_id=effective_mandant_id,
            invoice_name_long=invoice_name_long,
            voucher_title_lexware=voucher_title,
            address_name=customer_raw,
            address_street=str(group.get("adresse_roh", "")).strip(),
        )

        if contacts is not None:
            proposal.customer_match = self.customer_matcher.match_exact(customer_raw, contacts)
            if proposal.customer_match.state == "eindeutig":
                street = getattr(proposal.customer_match, "address_street", "")
                zip_code = getattr(proposal.customer_match, "address_zip", "")
                city = getattr(proposal.customer_match, "address_city", "")
                country = getattr(proposal.customer_match, "address_country", "")

                if isinstance(street, str) and street.strip():
                    proposal.address_street = street.strip()
                if isinstance(zip_code, str) and zip_code.strip():
                    proposal.address_zip = zip_code.strip()
                if isinstance(city, str) and city.strip():
                    proposal.address_city = city.strip()
                if isinstance(country, str) and country.strip():
                    proposal.address_country = country.strip()

        # Füge Positionen hinzu
        self.position_service.enrich_proposal_with_positions(proposal, group)

        # Validiere den Proposal
        self.validation_service.validate_proposal(proposal)

        return proposal

    def _build_group_key(self, group: dict) -> str:
        return "||".join([
            str(group.get("datum", "")).strip(),
            str(group.get("kunde_roh", "")).strip().lower(),
            str(group.get("projekt_roh", "")).strip().lower(),
        ])

    def _build_invoice_name(self, project_raw: str, start_date: str, end_date: str) -> str:
        project = project_raw or "Leistung"
        if start_date and end_date and start_date != end_date:
            return f"Rechnung {project} ({start_date} bis {end_date})"
        if start_date:
            return f"Rechnung {project} ({start_date})"
        return f"Rechnung {project}"

    def _build_lexware_title(self, project_raw: str) -> str:
        base = f"Rechnung {project_raw or 'Leistung'}".strip()
        return base[:25]
