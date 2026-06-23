# Rechnungsautomatismus

Tool zur Vorbereitung und zum Export von Angebots-/Rechnungsentwuerfen fuer Lexware auf Basis von Termin-/Einsatzdaten.

## Stand 2026-06-23

Aktueller Funktionsstand:
- Mandantenspezifische Kontakte und Artikel aus CSV sind aktiv
- Lexware-Export aus der GUI verfuegbar (`Angebot`/`Rechnung`, `Draft`/`Finalisieren`)
- Rechnungsvorschau vor Export verfuegbar
- Kundenzuordnung im Export robust (Kundennummer wird bevorzugt)
- Bearbeitungsdialog mit dynamischen Textregeln fuer Angebot/Rechnung
- Zahlungsbedingungen-Auswahl inkl. Faelligkeitsanzeige
- Artikeltexte (Titel/Kommentar) pro Gruppe editierbar und exportwirksam
- Tour-Filter (`Alle`, `Eintagestouren`, `Mehrtagestouren`) vorhanden
- PDF-Download nach Export optional aktivierbar
- PDF-Zielordner in der GUI sichtbar, inkl. Button zum Oeffnen
- Teststand: 112/112 Tests gruen (`pytest -q`)

## PDF-Konfiguration (.env)

Fuer automatischen PDF-Download:
- `LEXWARE_PDF_DOWNLOAD_ENABLED=true`
- `LEXWARE_PDF_DOWNLOADS_DIRECTORY=/workspaces/Rechnungsautomatismus/exports/pdfs`

Hinweise:
- Der Zielordner wird bei Bedarf automatisch erstellt
- Nach Aenderungen an `.env` die App neu starten

## Lexware-Link im Erfolgsdialog

Der Button "In Lexware oeffnen" erscheint nur, wenn gesetzt:
- `LEXWARE_WEB_URL_TEMPLATE=https://app.lexoffice.de/vouchers/{id}`

Ohne diese Variable wird kein Web-Link geoeffnet.

## Zugangsdaten sicher speichern

Echte Zugangsdaten nur lokal speichern und nie committen.

Empfohlen:
- `.env` im Projektroot (siehe `.env.example`)
- optional `config/lexware.local.json` (siehe `config/lexware.local.example.json`)

Wichtige Variablen:
- `LEXWARE_BASE_URL`
- `LEXWARE_CLIENT_ID`
- `LEXWARE_CLIENT_SECRET`
- `LEXWARE_ACCESS_TOKEN`
- `LEXWARE_REFRESH_TOKEN`
- `LEXWARE_TOKEN_URL`
- `LEXWARE_COMPANY_ID`

## Schnellstart

```bash
cd /workspaces/Rechnungsautomatismus
python -m app.main
```

## Tests

```bash
cd /workspaces/Rechnungsautomatismus
pytest -q
```
