from dataclasses import dataclass, field


@dataclass
class ValidationMessage:
    level: str
    field: str
    message: str


@dataclass
class ExportState:
    status: str = "neu"
    lexware_id: str = ""
    resource_uri: str = ""
    exported_at: str = ""
    error_message: str = ""


@dataclass
class CustomerMatchResult:
    state: str = "nicht_zugeordnet"
    customer_name: str = ""
    customer_number: str = ""
    address_street: str = ""
    address_zip: str = ""
    address_city: str = ""
    address_country: str = "DE"


@dataclass
class InvoicePosition:
    title: str
    description: str = ""
    quantity: float = 1.0
    unit: str = "Stk"
    unit_price_net: float = 0.0
    tax_rate: float = 19.0

    @property
    def total_net(self) -> float:
        return round(self.quantity * self.unit_price_net, 2)


@dataclass
class InvoiceProposal:
    source_group_key: str
    start_date: str
    end_date: str
    kw: str
    customer_raw: str
    project_raw: str
    employees: list[str] = field(default_factory=list)
    mandant_id: str = ""
    customer_match: CustomerMatchResult = field(default_factory=CustomerMatchResult)
    invoice_name_long: str = ""
    voucher_title_lexware: str = ""
    customer_reference: str = ""
    payment_terms_text: str = "14 Tage netto"
    address_name: str = ""
    address_street: str = ""
    address_zip: str = ""
    address_city: str = ""
    address_country: str = "DE"
    positions: list[InvoicePosition] = field(default_factory=list)
    validation_messages: list[ValidationMessage] = field(default_factory=list)
    export_state: ExportState = field(default_factory=ExportState)

    @property
    def is_export_ready(self) -> bool:
        return not any(msg.level == "error" for msg in self.validation_messages)
