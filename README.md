# Rechnungsautomatismus
Es wird ein Tool, welches Anhand der Temine Excel Rechnungen für Lexware vorbereitet

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
