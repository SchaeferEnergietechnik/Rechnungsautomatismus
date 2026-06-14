from dataclasses import dataclass

from PySide6.QtWidgets import QApplication

from app.config_loader import ConfigLoader
from gui.main_window import MainWindow
from importer.contacts_csv_importer import ContactsCsvImporter
from importer.employee_block_extractor import EmployeeBlockExtractor
from importer.excel_termin_importer import ExcelTerminImporter
from services.block_classification_service import BlockClassificationService
from services.grouping_service import GroupingService
from services.invoice_proposal_mapper_service import InvoiceProposalMapperService
from services.invoice_position_service import InvoicePositionService
from services.invoice_validation_service import InvoiceValidationService
from services.lexware_draft_export_service import LexwareDraftExportService
from services.proposal_builder_service import ProposalBuilderService


@dataclass
class AppContext:
    qt_app: QApplication
    main_window: MainWindow
    config_loader: ConfigLoader
    importer: ExcelTerminImporter
    contacts_importer: ContactsCsvImporter
    extractor: EmployeeBlockExtractor
    classifier: BlockClassificationService
    builder: ProposalBuilderService
    grouping: GroupingService
    invoice_mapper: InvoiceProposalMapperService
    invoice_position_service: InvoicePositionService
    invoice_validation_service: InvoiceValidationService
    lexware_export: LexwareDraftExportService


def bootstrap_application() -> AppContext:
    qt_app = QApplication([])

    config_loader = ConfigLoader()
    importer = ExcelTerminImporter()
    contacts_importer = ContactsCsvImporter()
    extractor = EmployeeBlockExtractor()
    classifier = BlockClassificationService()
    builder = ProposalBuilderService()
    grouping = GroupingService()
    position_service = InvoicePositionService()
    validation_service = InvoiceValidationService()
    invoice_mapper = InvoiceProposalMapperService(
        position_service=position_service,
        validation_service=validation_service,
    )
    lexware_export = LexwareDraftExportService()

    main_window = MainWindow(
        config_loader=config_loader,
        importer=importer,
        contacts_importer=contacts_importer,
        extractor=extractor,
        classifier=classifier,
        builder=builder,
        grouping=grouping,
        invoice_mapper=invoice_mapper,
        lexware_export_service=lexware_export,
    )

    main_window.load_file("data/termine.xlsx")

    return AppContext(
        qt_app=qt_app,
        main_window=main_window,
        config_loader=config_loader,
        importer=importer,
        contacts_importer=contacts_importer,
        extractor=extractor,
        classifier=classifier,
        builder=builder,
        grouping=grouping,
        invoice_mapper=invoice_mapper,
        invoice_position_service=position_service,
        invoice_validation_service=validation_service,
        lexware_export=lexware_export,
    )
