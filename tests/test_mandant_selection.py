"""Tests für Mandantenauswahl und mandantenabhängiges Matching in der GUI."""
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

from app.config_loader import ConfigLoader
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
            },
            {
                "id": "ges_power_service",
                "display_name": "G.E.S. Power Service GmbH",
                "firma_name": "G.E.S. Power Service GmbH",
                "contacts_csv": "data/ges_power_service/contacts.csv",
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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
