# Rechnungsautomatismus
Es wird ein Tool, welches Anhand der Temine Excel Rechnungen für Lexware vorbereitet

## Stand 2026-06-15

Aktueller Funktionsstand:
- Mandantenspezifische Kontakte und Artikel aus CSV sind aktiv.
- Mehrfach-Artikel pro Vorschlag sind in der GUI bearbeitbar.
- Lexware-Draft-Export aus der GUI ist produktiv vorhanden (inkl. Duplikat-Schutz).
- Draft-Felder sind editierbar und persistent:
	- Belegtitel
	- Einleitung
	- Nachbemerkung
	- Zahlungsziel
- Fahrtkostenlogik ist integriert:
	- Startadresse aus Mandant
	- Zieladresse aus Einsatz
	- echte Auto-Fahrstrecke (Routing)
	- robuste Koordinaten-/Adressverarbeitung
	- Modi `extra_article` und `included_in_first_article`
- Separates Angebots-/Rechnungsfenster ist vorhanden.
- Lexware-Textvorlagen werden per API geladen und kundenbezogen gefiltert.
- Kundenadresse fuer den Export wird aus gematchten Kundendaten (contacts.csv) uebernommen.
- Kundenmatch nutzt robusten CSV-Import mit Encoding-Fallback (utf-8-sig/cp1252/latin-1).
- Fahrtkostenberechnung und -abrechnung erfolgt fuer Hin- und Rueckfahrt.
- Angebotstext bei Fahrtkosten zeigt nur Stunden und KM (ohne EUR-Betraege im Text).
- Validierungsstatus ist in der GUI-Tabelle sichtbar.
- Detailansicht zeigt Validierungsmeldungen und Rechnungspositionsvorschau.
- Mapper nutzt `mandant_id` aus der Gruppe als Fallback (kein falscher Mandant-Fehler mehr).
- Sammel-Export blockiert bei harten Validierungsfehlern.
- Sammel-Export verlangt explizite Bestaetigung bei Warnungen und fehlender Geokodierung.
- Export-Bestaetigung zeigt Lexware-Konto-Kontext je Mandant (Mandant/Base URL/Endpoint/Company-ID).
- Rundreisen bei gleichem Kundentag mit mehreren Projekten werden verteilt:
	- Segmentierung Firma -> Projekt 1 -> ... -> letztes Projekt -> Firma
	- erste Rechnung = Anfahrt
	- letzte Rechnung = inkl. Rueckfahrt
	- Segmentrollen und Route/km/h in der Exportvorschau sichtbar
- Kundenspezifische Artikelsatz-Vorlagen sind verfuegbar (speichern/anwenden, persistiert in Projekt/Sitzung/Statusdatei).
- Schnellreferenz fuer Artikelauswahl ist aktiv (z. B. `1,4,7` mit Validierung und Duplikat-Schutz).
- Wahlregeln fuer Weiterfahrt und Mehrtagespauschale (Tag 1 / Tag 2) sind im Dialog konfigurierbar und wirksam.
- Teststand: 88/88 Tests gruen (`pytest -q`).

Update 2026-06-15:
- Stand aus `feature/mandant-specific-data` ist nach `main` gemerged.
- GitHub Actions CI ist wieder gruen (inkl. PySide6-Import in CI).
- Der Versuch, bestehende Lexware-Belege per API zu listen/finalisieren/PDF-seitig rueckwaerts zu bearbeiten, wurde verworfen.
- Laut offizieller Lexware-Doku sind fuer Invoices/Quotations `POST ...[?finalize=true]` und `GET .../{id}` dokumentiert, aber kein allgemeiner Listen-Endpoint und keine nachtraegliche Statusaenderung bestehender Belege.

## Lexware Zugangsdaten sicher speichern

Lege echte Zugangsdaten nur lokal ab und teile sie nicht im Chat.

Option A (empfohlen): `.env` im Projektroot
- Datei lokal anlegen: `.env`
- Beispielwerte siehe `.env.example`
- Diese Datei ist in `.gitignore` bereits ausgeschlossen.

Option B: lokale JSON-Konfiguration
- Datei lokal anlegen: `config/lexware.local.json`
- Beispielstruktur siehe `config/lexware.local.example.json`
- Diese Datei ist in `.gitignore` ausgeschlossen.

Empfohlene Umgebungsvariablen:
- `LEXWARE_BASE_URL`
- `LEXWARE_CLIENT_ID`
- `LEXWARE_CLIENT_SECRET`
- `LEXWARE_ACCESS_TOKEN`
- `LEXWARE_REFRESH_TOKEN`
- `LEXWARE_TOKEN_URL`
- `LEXWARE_COMPANY_ID`
- `LEXWARE_TEMPLATES_ENDPOINT` (optional, Default: `/v1/text-modules`)
- `LEXWARE_CUSTOMERS_ENDPOINT` (optional, Default: `/v1/contacts`)

Mandantenspezifische Lexware-Accounts (wichtig bei mehreren Firmen):
- Fuer jeden Mandanten koennen die Lexware-Zugangsdaten per ENV uebersteuert werden.
- Namensschema: `LEXWARE_<KEY>__<MANDANT_ID_IN_GROSSBUCHSTABEN>`
- Beispiel:
	- `ges_energietechnik` -> `LEXWARE_ACCESS_TOKEN__GES_ENERGIETECHNIK`
	- `ges_power_service` -> `LEXWARE_ACCESS_TOKEN__GES_POWER_SERVICE`
- Unterstuetzte Keys:
	- `BASE_URL`, `ACCESS_TOKEN`, `CLIENT_ID`, `CLIENT_SECRET`, `REFRESH_TOKEN`, `TOKEN_URL`, `COMPANY_ID`, `DRAFT_ENDPOINT`, `TEMPLATES_ENDPOINT`, `CUSTOMERS_ENDPOINT`
- Prioritaet/Fallback:
	- 1) mandantenspezifische ENV
	- 2) mandantenspezifische Werte in `config/mandants.json` (z. B. `lexware_company_id`)
	- 3) globale `LEXWARE_*` Werte

Wenn du mehrere Lexware-Accounts nutzt, kannst du je Mandant in `config/mandants.json` zusätzlich `lexware_company_id` pflegen. Der Export verwendet dann beim aktiven Mandanten diese Company-ID.

Die mandantenspezifischen CSV-Dateien liegen ohne Ausnahme unter:
- `data/ges_energietechnik/contacts.csv`
- `data/ges_energietechnik/produkte_services.csv`
- `data/ges_power_service/contacts.csv`
- `data/ges_power_service/produkte_services.csv`

Testmodus-Hinweis (Angebote statt Rechnungen):
- Standard fuer Draft-Export ist aktuell `LEXWARE_DRAFT_ENDPOINT=/v1/quotations`, damit Tests keine Rechnungen erzeugen.
- Fuer den spaeteren Echtbetrieb auf Rechnungen den Endpoint auf `LEXWARE_DRAFT_ENDPOINT=/v1/invoices` setzen.

Wichtige API-Grenze laut offizieller Lexware-Doku:
- Bestehende Invoices/Quotations sollen nicht ueber einen allgemeinen Listen-Dialog per API geladen werden.
- Die Finalisierung ist fuer diese Belegtypen beim Erzeugen ueber `finalize=true` vorgesehen, nicht nachtraeglich per PUT/PATCH.

Aktuell noch offen (naechster Ausbau):
- PDF-Open/Download-Flow fuer bekannte Lexware-Beleg-ID

Fahrtkostenlogik (MVP):
- Startadresse: aktive Mandantenadresse aus `config/mandants.json`
- Zieladresse: Einsatzadresse aus Termin-Excel (`adresse_roh`)
- KM werden automatisch als echte Auto-Fahrstrecke berechnet (Routing) und sind manuell anpassbar
- Standardwerte pro Rechnung:
	- `150 EUR/Stunde`
	- `0,70 EUR/km`
- Abrechnungsmodus pro Rechnung:
	- `extra_article`
	- `included_in_first_article`

Wichtig:
- Keine Zugangsdaten in versionierte JSON-Dateien unter `config/` eintragen.
- Keine Zugangsdaten per Git committen.
- Wenn ein Secret versehentlich committed wurde: Secret sofort rotieren.

## App in Codespaces starten

1. Terminal in VS Code öffnen.
2. In den Projektordner wechseln:

```bash
cd /workspaces/Rechnungsautomatismus
```

3. Optional virtuelles Environment erstellen/aktivieren:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

4. Abhängigkeiten installieren:

```bash
pip install PySide6 openpyxl
```

5. `.env` aus Vorlage anlegen und befüllen:

```bash
cp .env.example .env
```

6. App starten:

```bash
python -m app.main
```

Wenn `python` nicht gefunden wird, stattdessen `python3 -m app.main` verwenden.

## Token-Refresh (kurz)

- Wenn `LEXWARE_ACCESS_TOKEN` abläuft, versucht die App automatisch zu erneuern.
- Dafür müssen gesetzt sein:
	- `LEXWARE_CLIENT_ID`
	- `LEXWARE_CLIENT_SECRET`
	- `LEXWARE_REFRESH_TOKEN`
	- `LEXWARE_TOKEN_URL`

## Codespaces ohne GUI (empfohlen)

In GitHub Codespaces gibt es meist kein Linux-Desktop-Display. Deshalb kann die Qt-GUI mit `xcb`-Fehler abbrechen.

Für Funktionstests nutze den CLI-Modus:

```bash
cd /workspaces/Rechnungsautomatismus
python -m app.cli_export_test --dry-run --limit 1
```

Echter Export (ohne `--dry-run`):

```bash
python -m app.cli_export_test --limit 1
```

Alle offenen Einsätze exportieren:

```bash
python -m app.cli_export_test --all
```

Hinweise:
- `--dry-run` zeigt nur die erzeugte Payload und sendet nichts an Lexware.
- Standardmäßig werden nur offene `einsatz`-Gruppen genommen.
- Mit `--include-review` werden auch `prueffall`-Gruppen einbezogen.

## Branch-Workflow (ab jetzt)

- `main` bleibt stabil.
- Neue Entwicklung immer in `feature/*` oder `fix/*`.
- Merge nach `main` nur mit gruener CI und GUI-Smoketest.

Siehe auch `CONTRIBUTING.md` fuer den konkreten Ablauf.

## GitHub Actions CI

Automatisch eingerichtet:
- Workflow: `.github/workflows/ci.yml`
- Testframework: `pytest`
- Tests liegen unter `tests/`

Die CI laeuft auf Push (`main`, `feature/*`, `fix/*`) und auf Pull Requests gegen `main`.
