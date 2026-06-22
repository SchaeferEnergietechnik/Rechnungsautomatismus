"""Tests für PDF-Download."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from services.lexware_draft_export_service import LexwareDraftExportService


def test_download_voucher_pdf_not_configured_returns_error(monkeypatch):
    """Test: PDF-Download blockiert wenn nicht konfiguriert."""
    monkeypatch.delenv("LEXWARE_PDF_DOWNLOAD_ENABLED", raising=False)
    monkeypatch.delenv("LEXWARE_PDF_DOWNLOADS_DIRECTORY", raising=False)
    
    service = LexwareDraftExportService()
    result = service.download_voucher_pdf("test-id")
    
    assert result["success"] is False
    assert "nicht konfiguriert" in result["error"].lower()
    assert result["filepath"] == ""


def test_download_voucher_pdf_creates_directory(monkeypatch, tmp_path):
    """Test: Download-Verzeichnis wird erstellt wenn nicht vorhanden."""
    download_dir = tmp_path / "pdfs"
    monkeypatch.setenv("LEXWARE_PDF_DOWNLOAD_ENABLED", "true")
    monkeypatch.setenv("LEXWARE_PDF_DOWNLOADS_DIRECTORY", str(download_dir))
    monkeypatch.setenv("LEXWARE_BASE_URL", "https://api.test.de")
    monkeypatch.setenv("LEXWARE_ACCESS_TOKEN", "test-token")
    
    service = LexwareDraftExportService()
    
    # Mock urlopen für erfolgreiches Download
    with patch('services.lexware_draft_export_service.request.urlopen') as mock_urlopen:
        mock_response = MagicMock()
        mock_response.read.return_value = b"PDF content here"
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        result = service.download_voucher_pdf("voucher-123")
        
        assert result["success"] is True
        assert download_dir.exists()
        assert "voucher-123" in result["filepath"]


def test_download_voucher_pdf_filename_generation(monkeypatch, tmp_path):
    """Test: Dateiname wird aus Voucher-ID generiert wenn nicht übergeben."""
    download_dir = tmp_path / "pdfs"
    download_dir.mkdir(parents=True)
    
    monkeypatch.setenv("LEXWARE_PDF_DOWNLOAD_ENABLED", "true")
    monkeypatch.setenv("LEXWARE_PDF_DOWNLOADS_DIRECTORY", str(download_dir))
    monkeypatch.setenv("LEXWARE_BASE_URL", "https://api.test.de")
    monkeypatch.setenv("LEXWARE_ACCESS_TOKEN", "test-token")
    
    service = LexwareDraftExportService()
    
    with patch('services.lexware_draft_export_service.request.urlopen') as mock_urlopen:
        mock_response = MagicMock()
        mock_response.read.return_value = b"PDF content"
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        result = service.download_voucher_pdf("abc-def-ghi")
        
        assert result["success"] is True
        filepath = Path(result["filepath"])
        assert filepath.name == "beleg_abc-def-ghi.pdf"
        assert filepath.exists()


def test_download_voucher_pdf_custom_filename(monkeypatch, tmp_path):
    """Test: Benutzerdefinierten Dateinamen verwenden."""
    download_dir = tmp_path / "pdfs"
    download_dir.mkdir(parents=True)
    
    monkeypatch.setenv("LEXWARE_PDF_DOWNLOAD_ENABLED", "true")
    monkeypatch.setenv("LEXWARE_PDF_DOWNLOADS_DIRECTORY", str(download_dir))
    monkeypatch.setenv("LEXWARE_BASE_URL", "https://api.test.de")
    monkeypatch.setenv("LEXWARE_ACCESS_TOKEN", "test-token")
    
    service = LexwareDraftExportService()
    
    with patch('services.lexware_draft_export_service.request.urlopen') as mock_urlopen:
        mock_response = MagicMock()
        mock_response.read.return_value = b"PDF content"
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        result = service.download_voucher_pdf("abc-123", filename="meine_rechnung.pdf")
        
        assert result["success"] is True
        filepath = Path(result["filepath"])
        assert filepath.name == "meine_rechnung.pdf"
