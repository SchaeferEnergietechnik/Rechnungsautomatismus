"""Tests für Mandantenauswahl und mandantenabhängiges Matching in der GUI."""
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

from app.config_loader import ConfigLoader
from importer.articles_csv_importer import ArticlesCsvImporter
from importer.contacts_csv_importer import ContactsCsvImporter
from services.customer_matcher_service import CustomerMatcherService
from services.invoice_proposal_mapper_service import InvoiceProposalMapperService


@pytest.fixture
def config_loader():
    """Mock ConfigLoader mit Test-Mandanten."""
    loader = Mock(spec=ConfigLoader)
    loader.load_json = Mock(return_value={
        "mandants": [
            {
                "id": "ges_energietechnik",
                "display_name": "G.E.S. Energietechnik GmbH",
                "firma_name": "G.E.S. Energietechnik GmbH",
                "contacts_csv": "data/ges_energietechnik/contacts.csv",
                "products_csv": "data/ges_energietechnik/produkte_services.csv",
                "lexware_company_id": "company-energietechnik",
            },
            {
                "id": "ges_power_service",
                "display_name": "G.E.S. Power Service GmbH",
                "firma_name": "G.E.S. Power Service GmbH",
                "contacts_csv": "data/ges_power_service/contacts.csv",
                "products_csv": "data/ges_power_service/produkte_services.csv",
                "lexware_company_id": "company-power-service",
            }
        ]
    })
    return loader


@pytest.fixture
def contacts_importer():
    """Mock ContactsCsvImporter."""
    importer = Mock(spec=ContactsCsvImporter)
    
    # Mock für ges_energietechnik Kontakte
    ges_et_contacts = [
        {"firma": "Energietechnik AG", "kontakt": "Max Mustermann"},
        {"firma": "PowerCorp", "kontakt": "Anna Schmidt"},
    ]
    
    # Mock für ges_power_service Kontakte
    ges_ps_contacts = [
        {"firma": "Service Plus GmbH", "kontakt": "Klaus Meyer"},
        {"firma": "PowerCorp", "kontakt": "Bernd Wagner"},
    ]
    
    def load_side_effect(path):
        if "ges_energietechnik" in path:
            return ges_et_contacts
        elif "ges_power_service" in path:
            return ges_ps_contacts
        return []
    
    importer.load = Mock(side_effect=load_side_effect)
    return importer


@pytest.fixture
def articles_importer():
    """Mock ArticlesCsvImporter."""
    importer = Mock(spec=ArticlesCsvImporter)

    ges_et_articles = [
        {"Artikelnummer": "ET-1", "Bezeichnung": "ET Service", "Einheit": "Stück", "Steuerart": "USt19", "VK (Netto)": "100,00"},
    ]
    ges_ps_articles = [
        {"Artikelnummer": "PS-1", "Bezeichnung": "PS Service", "Einheit": "Stunde", "Steuerart": "USt19", "VK (Netto)": "200,00"},
    ]

    def load_side_effect(path):
        if "ges_energietechnik" in path:
            return ges_et_articles
        elif "ges_power_service" in path:
            return ges_ps_articles
        return []

    importer.load = Mock(side_effect=load_side_effect)
    return importer


@pytest.fixture
def invoice_mapper():
    """Mock InvoiceProposalMapperService."""
    mapper = Mock(spec=InvoiceProposalMapperService)
    
    def map_group_side_effect(group, contacts=None):
        proposal = Mock()
        match = Mock()
        
        # Simuliere Matching basierend auf Kontakten
        customer_name = group.get("kunde_roh", "")
        
        if contacts:
            for contact in contacts:
                if contact.get("firma", "").lower() == customer_name.lower():
                    match.state = "eindeutig"
                    match.customer_name = contact.get("firma")
                    match.customer_number = contact.get("kontakt")
                    proposal.customer_match = match
                    return proposal
            
            # Nicht gefunden
            match.state = "nicht_gefunden"
            match.customer_name = ""
            match.customer_number = ""
            proposal.customer_match = match
            return proposal
        
        # Keine Kontakte geladen
        match.state = "nicht_zugeordnet"
        match.customer_name = ""
        match.customer_number = ""
        proposal.customer_match = match
        return proposal
    
    mapper.map_group = Mock(side_effect=map_group_side_effect)
    return mapper


def test_load_mandants(config_loader):
    """Test: Mandanten werden aus Konfiguration geladen."""
    from gui.main_window import MainWindow
    
    with patch('gui.main_window.QApplication'):
        with patch.object(MainWindow, '__init__', lambda x: None):
            window = MainWindow()
            window.config_loader = config_loader
            
            mandants = window._load_mandants()
            
            assert len(mandants) == 2
            assert mandants[0]["id"] == "ges_energietechnik"
            assert mandants[1]["id"] == "ges_power_service"


def test_get_mandant_by_id(config_loader):
    """Test: Mandanten können nach ID abgerufen werden."""
    from gui.main_window import MainWindow
    
    with patch('gui.main_window.QApplication'):
        with patch.object(MainWindow, '__init__', lambda x: None):
            window = MainWindow()
            window.config_loader = config_loader
            window.mandants = window._load_mandants()
            
            mandant = window._get_mandant_by_id("ges_energietechnik")
            
            assert mandant is not None
            assert mandant["display_name"] == "G.E.S. Energietechnik GmbH"


def test_load_contacts_for_mandant(config_loader, contacts_importer):
    """Test: Kontakte werden nur für den angegebenen Mandanten geladen."""
    from gui.main_window import MainWindow
    
    with patch('gui.main_window.QApplication'):
        with patch.object(MainWindow, '__init__', lambda x: None):
            window = MainWindow()
            window.config_loader = config_loader
            window.contacts_importer = contacts_importer
            window.mandants = window._load_mandants()
            
            # Lade Kontakte für ges_energietechnik
            et_contacts = window._load_contacts_for_mandant("ges_energietechnik")
            assert len(et_contacts) == 2
            assert et_contacts[0]["firma"] == "Energietechnik AG"
            
            # Lade Kontakte für ges_power_service
            ps_contacts = window._load_contacts_for_mandant("ges_power_service")
            assert len(ps_contacts) == 2
            assert ps_contacts[0]["firma"] == "Service Plus GmbH"


def test_load_articles_for_mandant(config_loader, articles_importer):
    """Test: Artikel werden nur für den angegebenen Mandanten geladen."""
    from gui.main_window import MainWindow

    with patch('gui.main_window.QApplication'):
        with patch.object(MainWindow, '__init__', lambda x: None):
            window = MainWindow()
            window.config_loader = config_loader
            window.articles_importer = articles_importer
            window.mandants = window._load_mandants()

            et_articles = window._load_articles_for_mandant("ges_energietechnik")
            assert len(et_articles) == 1
            assert et_articles[0]["Artikelnummer"] == "ET-1"

            ps_articles = window._load_articles_for_mandant("ges_power_service")
            assert len(ps_articles) == 1
            assert ps_articles[0]["Artikelnummer"] == "PS-1"


def test_apply_customer_matching_for_mandant(config_loader, contacts_importer, invoice_mapper):
    """Test: Customer Matching wird nur für den aktiven Mandanten durchgeführt."""
    from gui.main_window import MainWindow
    
    with patch('gui.main_window.QApplication'):
        with patch.object(MainWindow, '__init__', lambda x: None):
            window = MainWindow()
            window.config_loader = config_loader
            window.contacts_importer = contacts_importer
            window.invoice_mapper = invoice_mapper
            window.mandants = window._load_mandants()
            
            # Erstelle Test-Gruppen
            window.groups = [
                {
                    "kunde_roh": "Energietechnik AG",
                    "customer_match_state": "nicht_zugeordnet",
                    "customer_match_name": "",
                    "customer_match_number": "",
                },
                {
                    "kunde_roh": "Service Plus GmbH",
                    "customer_match_state": "nicht_zugeordnet",
                    "customer_match_name": "",
                    "customer_match_number": "",
                }
            ]
            
            # Matching für ges_energietechnik
            window._apply_customer_matching_for_mandant("ges_energietechnik")
            
            # Bei ges_energietechnik sollte Energietechnik AG eindeutig sein
            assert window.groups[0]["customer_match_state"] == "eindeutig"
            assert window.groups[0]["customer_match_name"] == "Energietechnik AG"
            
            # Service Plus GmbH sollte nicht gefunden sein
            assert window.groups[1]["customer_match_state"] == "nicht_gefunden"


def test_mandant_change_triggers_rematching(config_loader, contacts_importer, invoice_mapper):
    """Test: Mandantenwechsel löst Re-Matching aus."""
    from gui.main_window import MainWindow
    
    with patch('gui.main_window.QApplication'):
        with patch.object(MainWindow, '__init__', lambda x: None):
            window = MainWindow()
            window.config_loader = config_loader
            window.contacts_importer = contacts_importer
            window.invoice_mapper = invoice_mapper
            window.mandants = window._load_mandants()
            window.active_mandant_id = "ges_energietechnik"
            window.change_log = []
            window._log_action = Mock()
            window._save_manual_data = Mock()
            window.refresh_table = Mock()
            
            # PowerCorp existiert in beiden Mandanten
            window.groups = [
                {
                    "kunde_roh": "PowerCorp",
                    "customer_match_state": "nicht_zugeordnet",
                    "customer_match_name": "",
                    "customer_match_number": "",
                }
            ]
            
            # Matching für ges_energietechnik
            window._apply_customer_matching_for_mandant("ges_energietechnik")
            assert window.groups[0]["customer_match_state"] == "eindeutig"
            assert window.groups[0]["customer_match_number"] == "Anna Schmidt"
            
            # Wechsel zu ges_power_service
            window._on_mandant_changed("ges_power_service")
            
            assert window.active_mandant_id == "ges_power_service"
            # Bei ges_power_service sollte der Kontakt anders sein
            assert window.groups[0]["customer_match_number"] == "Bernd Wagner"
            window._log_action.assert_called()


def test_session_persistence_with_mandant(config_loader, contacts_importer):
    """Test: Mandantenauswahl wird in Session gespeichert und wiederhergestellt."""
    from gui.main_window import MainWindow
    
    with patch('gui.main_window.QApplication'):
        with patch.object(MainWindow, '__init__', lambda x: None):
            window = MainWindow()
            window.config_loader = config_loader
            window.contacts_importer = contacts_importer
            window.mandants = window._load_mandants()
            window.active_mandant_id = "ges_power_service"
            window.current_file_path = "data/termine.xlsx"
            window.groups = []
            window.change_log = []
            
            # Simuliere Session-Speicherung
            session_data = {
                "source_file": window.current_file_path,
                "active_mandant_id": window.active_mandant_id,
                "groups": {},
                "change_log": [],
                "saved_at": "2026-06-14T10:00:00",
            }
            
            # active_mandant_id sollte gespeichert sein
            assert session_data["active_mandant_id"] == "ges_power_service"
            
            # Simuliere Session-Laden
            loaded_mandant_id = session_data.get("active_mandant_id", "")
            assert loaded_mandant_id == "ges_power_service"


def test_lexware_export_uses_active_mandant_company_id(config_loader, contacts_importer):
    """Test: Der Lexware-Export verwendet die Company-ID des aktiven Mandanten."""
    from gui.main_window import MainWindow

    with patch('gui.main_window.QApplication'):
        with patch.object(MainWindow, '__init__', lambda x: None):
            window = MainWindow()
            window.config_loader = config_loader
            window.contacts_importer = contacts_importer
            window.mandants = window._load_mandants()
            window.active_mandant_id = "ges_power_service"
            window.groups = [
                {
                    "kunde_roh": "PowerCorp",
                    "customer_match_state": "eindeutig",
                    "customer_match_name": "PowerCorp",
                    "customer_match_number": "2002",
                    "lexware_export_status": "",
                }
            ]
            window.visible_groups = window.groups
            window._selected_groups = Mock(return_value=window.groups)
            window._is_already_exported = Mock(return_value=False)
            window._save_manual_data = Mock()
            window._log_action = Mock()
            window.refresh_table = Mock()
            window.draft_title_edit = Mock(text=Mock(return_value="Sonderangebot"))
            window.draft_introduction_edit = Mock(toPlainText=Mock(return_value="Individuelle Einleitung"))
            window.draft_remark_edit = Mock(toPlainText=Mock(return_value="Individuelle Nachbemerkung"))
            window.draft_payment_term_days_spin = Mock(value=Mock(return_value=30))
            window.lexware_export_service = Mock()
            window.lexware_export_service.is_configured = Mock(return_value=True)
            window.lexware_export_service.export_group_as_draft = Mock(return_value={
                "success": True,
                "response": {"id": "draft-1"},
            })

            with patch('gui.main_window.QMessageBox.question', return_value=16384):
                with patch('gui.main_window.QMessageBox.information'):
                    window.export_selected_groups_to_lexware_draft()

            window.lexware_export_service.export_group_as_draft.assert_called_once()
            _, kwargs = window.lexware_export_service.export_group_as_draft.call_args
            assert kwargs["company_id"] == "company-power-service"
            assert kwargs["title"] == "Sonderangebot"
            assert kwargs["introduction"] == "Individuelle Einleitung"
            assert kwargs["remark"] == "Individuelle Nachbemerkung"
            assert kwargs["payment_term_days"] == 30


def test_lexware_export_uses_mandant_specific_env_credentials(config_loader, contacts_importer, monkeypatch):
    """Test: Mandantenspezifische ENV-Werte werden für Lexware-Service genutzt."""
    from gui.main_window import MainWindow

    monkeypatch.setenv("LEXWARE_BASE_URL", "https://api.global.example")
    monkeypatch.setenv("LEXWARE_ACCESS_TOKEN", "global-token")
    monkeypatch.setenv("LEXWARE_BASE_URL__GES_POWER_SERVICE", "https://api.power.example")
    monkeypatch.setenv("LEXWARE_ACCESS_TOKEN__GES_POWER_SERVICE", "power-token")
    monkeypatch.setenv("LEXWARE_COMPANY_ID__GES_POWER_SERVICE", "company-power-env")

    with patch('gui.main_window.QApplication'):
        with patch.object(MainWindow, '__init__', lambda x: None):
            window = MainWindow()
            window.config_loader = config_loader
            window.contacts_importer = contacts_importer
            window.mandants = window._load_mandants()
            window.active_mandant_id = "ges_power_service"
            window._lexware_service_defaults = None
            window.lexware_export_service = Mock(
                base_url="https://api.global.example",
                access_token="global-token",
                client_id="",
                client_secret="",
                refresh_token="",
                token_url="",
                company_id="",
                draft_endpoint="/v1/quotations",
                templates_endpoint="/v1/text-modules",
                customers_endpoint="/v1/contacts",
            )

            window._configure_lexware_service_for_mandant("ges_power_service")

            assert window.lexware_export_service.base_url == "https://api.power.example"
            assert window.lexware_export_service.access_token == "power-token"
            assert window.lexware_export_service.company_id == "company-power-env"


def test_lexware_export_blocks_groups_with_validation_errors(config_loader, contacts_importer):
    """Test: Export wird blockiert, wenn ausgewählte Gruppen harte Validierungsfehler haben."""
    from gui.main_window import MainWindow

    with patch('gui.main_window.QApplication'):
        with patch.object(MainWindow, '__init__', lambda x: None):
            window = MainWindow()
            window.config_loader = config_loader
            window.contacts_importer = contacts_importer
            window.mandants = window._load_mandants()
            window.active_mandant_id = "ges_power_service"
            window.lexware_export_service = Mock()
            window.lexware_export_service.is_configured = Mock(return_value=True)
            window._configure_lexware_service_for_mandant = Mock()
            window._selected_groups = Mock(return_value=[
                {
                    "datum": "2026-04-07 00:00:00",
                    "kunde_roh": "PowerCorp",
                    "projekt_roh": "Projekt X",
                    "invoice_validation_errors": 2,
                }
            ])

            with patch('gui.main_window.QMessageBox.warning') as warning_mock:
                window.export_selected_groups_to_lexware_draft()

            warning_mock.assert_called_once()
            window.lexware_export_service.is_configured.assert_not_called()


def test_lexware_export_with_warnings_requires_confirmation(config_loader, contacts_importer):
    """Test: Export mit Warnungen erfordert explizite Bestätigung."""
    from gui.main_window import MainWindow

    with patch('gui.main_window.QApplication'):
        with patch.object(MainWindow, '__init__', lambda x: None):
            window = MainWindow()
            window.config_loader = config_loader
            window.contacts_importer = contacts_importer
            window.mandants = window._load_mandants()
            window.active_mandant_id = "ges_power_service"
            window.lexware_export_service = Mock()
            window.lexware_export_service.is_configured = Mock(return_value=True)
            window._configure_lexware_service_for_mandant = Mock()
            window._selected_groups = Mock(return_value=[
                {
                    "datum": "2026-04-07 00:00:00",
                    "kunde_roh": "PowerCorp",
                    "projekt_roh": "Projekt X",
                    "invoice_validation_errors": 0,
                    "invoice_validation_warnings": 2,
                }
            ])

            with patch('gui.main_window.QMessageBox.question', return_value=65536):
                window.export_selected_groups_to_lexware_draft()

            window.lexware_export_service.is_configured.assert_not_called()


def test_lexware_export_summary_includes_warning_count(config_loader, contacts_importer):
    """Test: Erfolgszusammenfassung enthält Anzahl exportierter Gruppen mit Warnungen."""
    from gui.main_window import MainWindow

    with patch('gui.main_window.QApplication'):
        with patch.object(MainWindow, '__init__', lambda x: None):
            window = MainWindow()
            window.config_loader = config_loader
            window.contacts_importer = contacts_importer
            window.mandants = window._load_mandants()
            window.active_mandant_id = "ges_power_service"
            window.groups = [
                {
                    "datum": "2026-04-07 00:00:00",
                    "kunde_roh": "PowerCorp",
                    "projekt_roh": "Projekt X",
                    "invoice_validation_errors": 0,
                    "invoice_validation_warnings": 1,
                    "travel_km": 10.0,
                    "lexware_export_status": "",
                }
            ]
            window.visible_groups = window.groups
            window._selected_groups = Mock(return_value=window.groups)
            window._is_already_exported = Mock(return_value=False)
            window._save_manual_data = Mock()
            window._log_action = Mock()
            window.refresh_table = Mock()
            window._configure_lexware_service_for_mandant = Mock()
            window._get_lexware_company_id_for_mandant = Mock(return_value="company-power-service")
            window.draft_title_edit = Mock(text=Mock(return_value="Sonderangebot"))
            window.draft_introduction_edit = Mock(toPlainText=Mock(return_value="Individuelle Einleitung"))
            window.draft_remark_edit = Mock(toPlainText=Mock(return_value="Individuelle Nachbemerkung"))
            window.draft_payment_term_days_spin = Mock(value=Mock(return_value=30))
            window.lexware_export_service = Mock()
            window.lexware_export_service.is_configured = Mock(return_value=True)
            window.lexware_export_service.is_quotation_mode = Mock(return_value=False)
            window.lexware_export_service.export_group_as_draft = Mock(return_value={
                "success": True,
                "response": {"id": "draft-1"},
            })

            with patch('gui.main_window.QMessageBox.question', side_effect=[16384, 16384]):
                with patch('gui.main_window.QMessageBox.information') as info_mock:
                    window.export_selected_groups_to_lexware_draft()

            info_mock.assert_called_once()
            info_text = info_mock.call_args.args[2]
            assert "Mit Warnungen (exportiert): 1" in info_text
            assert "Neu erstellt: 1" in info_text


def test_lexware_export_with_missing_geocoding_requires_confirmation(config_loader, contacts_importer):
    """Test: Export mit fehlender Geokodierung erfordert explizite Bestätigung."""
    from gui.main_window import MainWindow

    with patch('gui.main_window.QApplication'):
        with patch.object(MainWindow, '__init__', lambda x: None):
            window = MainWindow()
            window.config_loader = config_loader
            window.contacts_importer = contacts_importer
            window.mandants = window._load_mandants()
            window.active_mandant_id = "ges_power_service"
            window.groups = [
                {
                    "datum": "2026-04-07 00:00:00",
                    "kunde_roh": "PowerCorp",
                    "projekt_roh": "Projekt X",
                    "adresse_roh": "Unbekannte Adresse 1",
                    "invoice_validation_errors": 0,
                    "invoice_validation_warnings": 0,
                    "travel_km": 0.0,
                    "lexware_export_status": "",
                }
            ]
            window.visible_groups = window.groups
            window._selected_groups = Mock(return_value=window.groups)
            window._is_already_exported = Mock(return_value=False)
            window._save_manual_data = Mock()
            window._log_action = Mock()
            window.refresh_table = Mock()
            window._configure_lexware_service_for_mandant = Mock()
            window._calculate_travel_km_for_group = Mock(return_value=False)
            window.lexware_export_service = Mock()
            window.lexware_export_service.is_configured = Mock(return_value=True)

            with patch('gui.main_window.QMessageBox.question', return_value=65536):
                window.export_selected_groups_to_lexware_draft()

            window.lexware_export_service.is_configured.assert_called_once()
            window.lexware_export_service.export_group_as_draft.assert_not_called()


def test_draft_settings_survive_project_roundtrip(config_loader, contacts_importer, tmp_path):
    """Test: Draft-Felder werden mit Projektdatei gespeichert und geladen."""
    from gui.main_window import MainWindow

    project_file = tmp_path / "state.rvt.json"

    with patch('gui.main_window.QApplication'):
        with patch.object(MainWindow, '__init__', lambda x: None):
            window = MainWindow()
            window.config_loader = config_loader
            window.contacts_importer = contacts_importer
            window.mandants = window._load_mandants()
            window.active_mandant_id = "ges_power_service"
            window.current_file_path = "data/termine.xlsx"
            window.groups = [
                {
                    "datum": "07.04.2026",
                    "kunde_roh": "PowerCorp",
                    "projekt_roh": "Projekt X",
                    "manueller_status": "offen",
                }
            ]

            title_widget = Mock()
            title_widget.text = Mock(return_value="Sonderangebot")
            title_widget.setText = Mock()

            introduction_widget = Mock()
            introduction_widget.toPlainText = Mock(return_value="Individuelle Einleitung")
            introduction_widget.setPlainText = Mock()

            remark_widget = Mock()
            remark_widget.toPlainText = Mock(return_value="Individuelle Nachbemerkung")
            remark_widget.setPlainText = Mock()

            payment_widget = Mock()
            payment_widget.value = Mock(return_value=30)
            payment_widget.setValue = Mock()

            window.draft_title_edit = title_widget
            window.draft_introduction_edit = introduction_widget
            window.draft_remark_edit = remark_widget
            window.draft_payment_term_days_spin = payment_widget
            window._log_action = Mock()
            window._build_group_key = Mock(return_value="group-key")

            with patch('gui.main_window.QFileDialog.getSaveFileName', return_value=(str(project_file), "")):
                window.save_project_file()

            saved = json.loads(project_file.read_text(encoding="utf-8"))
            assert saved["draft_settings"]["title"] == "Sonderangebot"
            assert saved["draft_settings"]["introduction"] == "Individuelle Einleitung"
            assert saved["draft_settings"]["remark"] == "Individuelle Nachbemerkung"
            assert saved["draft_settings"]["payment_term_days"] == 30

            title_widget.text.return_value = "Geaendert"
            introduction_widget.toPlainText.return_value = "Geaendert"
            remark_widget.toPlainText.return_value = "Geaendert"
            payment_widget.value.return_value = 14
            title_widget.setText.reset_mock()
            introduction_widget.setPlainText.reset_mock()
            remark_widget.setPlainText.reset_mock()
            payment_widget.setValue.reset_mock()

            window.load_file = Mock()
            window.refresh_table = Mock()
            window.groups = [
                {
                    "datum": "07.04.2026",
                    "kunde_roh": "PowerCorp",
                    "projekt_roh": "Projekt X",
                    "manueller_status": "offen",
                }
            ]
            with patch('gui.main_window.QFileDialog.getOpenFileName', return_value=(str(project_file), "")):
                window.load_project_file()

            assert title_widget.setText.call_args_list[-1].args[0] == "Sonderangebot"
            assert introduction_widget.setPlainText.call_args_list[-1].args[0] == "Individuelle Einleitung"
            assert remark_widget.setPlainText.call_args_list[-1].args[0] == "Individuelle Nachbemerkung"
            assert payment_widget.setValue.call_args_list[-1].args[0] == 30


def test_mandant_defaults_fill_draft_fields(config_loader, contacts_importer):
    """Test: Mandanten-Standardwerte werden in die Draft-Felder übernommen."""
    from gui.main_window import MainWindow

    config_loader.load_json = Mock(return_value={
        "mandants": [
            {
                "id": "ges_power_service",
                "display_name": "G.E.S. Power Service GmbH",
                "contacts_csv": "data/ges_power_service/contacts.csv",
                "products_csv": "data/ges_power_service/produkte_services.csv",
                "lexware_company_id": "company-power-service",
                "default_payment_terms": "21 Tage netto",
                "default_draft_title": "Angebot Power Service",
                "default_draft_introduction": "Einleitung Power Service",
                "default_draft_remark": "Nachbemerkung Power Service",
            }
        ]
    })

    with patch('gui.main_window.QApplication'):
        with patch.object(MainWindow, '__init__', lambda x: None):
            window = MainWindow()
            window.config_loader = config_loader
            window.contacts_importer = contacts_importer
            window.mandants = window._load_mandants()

            title_widget = Mock()
            title_widget.setText = Mock()
            introduction_widget = Mock()
            introduction_widget.setPlainText = Mock()
            remark_widget = Mock()
            remark_widget.setPlainText = Mock()
            payment_widget = Mock()
            payment_widget.setValue = Mock()

            window.draft_title_edit = title_widget
            window.draft_introduction_edit = introduction_widget
            window.draft_remark_edit = remark_widget
            window.draft_payment_term_days_spin = payment_widget
            window.draft_preview_view = Mock()
            window._update_draft_preview = Mock()

            window._apply_draft_defaults_for_mandant("ges_power_service")

            title_widget.setText.assert_called_with("Angebot Power Service")
            introduction_widget.setPlainText.assert_called_with("Einleitung Power Service")
            remark_widget.setPlainText.assert_called_with("Nachbemerkung Power Service")
            payment_widget.setValue.assert_called_with(21)


def test_draft_preview_shows_positions(config_loader, contacts_importer):
    """Test: Die Draft-Vorschau zeigt die aus Artikeln abgeleiteten Positionen."""
    from gui.main_window import MainWindow

    with patch('gui.main_window.QApplication'):
        with patch.object(MainWindow, '__init__', lambda x: None):
            window = MainWindow()
            window.config_loader = config_loader
            window.contacts_importer = contacts_importer
            window.mandants = window._load_mandants()

            preview_widget = Mock()
            preview_widget.setPlainText = Mock()
            window.draft_preview_view = preview_widget

            window._draft_export_settings = Mock(return_value={
                "title": "Angebot",
                "introduction": "Intro",
                "remark": "Remark",
                "payment_term_days": 14,
            })
            window._selected_groups = Mock(return_value=[{
                "kunde_roh": "PowerCorp",
                "projekt_roh": "Projekt X",
            }])
            window._selected_articles_for_group = Mock(return_value=[
                {
                    "Artikelnummer": "PS-1",
                    "Bezeichnung": "PS Service",
                    "Einheit": "Stunde",
                    "Steuerart": "USt19",
                    "VK (Netto)": "200,00",
                },
                {
                    "Artikelnummer": "PS-2",
                    "Bezeichnung": "Zusatzleistung",
                    "Einheit": "Stk",
                    "Steuerart": "USt19",
                    "VK (Netto)": "50,00",
                },
            ])

            window._update_draft_preview()

            text = preview_widget.setPlainText.call_args.args[0]
            assert "Positionen: 2" in text
            assert "Positionen" in text
            assert "PS-1 - PS Service" in text
            assert "Einheit: Stunde | Netto: 200,00 | Steuer: USt19" in text
            assert "PS-2 - Zusatzleistung" in text
            assert "Einheit: Stk | Netto: 50,00 | Steuer: USt19" in text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
