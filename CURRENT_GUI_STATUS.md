# CURRENT GUI STATUS
## Aktueller Stand der vorhandenen GUI

Stand: 2026-06-22 (2. Update)
Letztes Update: 2026-06-22

Kurzstatistik:
- Teststand: 109/109 Tests gruen (`pytest -q`)
- Kundenadresse im Export aus Kundenmatch statt Projektadresse
- Fahrtkostenberechnung als Hin- und Rueckfahrt
- GUI zeigt Validierungsstatus in der Tabelle
- Detailansicht zeigt Validierungsmeldungen und Rechnungspositionsvorschau
- Sammel-Export blockiert bei harten Validierungsfehlern
- Warnungen und fehlende Geokodierung sind vor Export bestaetigungspflichtig
- Export-Bestaetigung zeigt Lexware Konto-Kontext (Mandant/Base-URL/Endpoint/Company-ID)
- Rundreisen fuer Kundentag mit mehreren Projekten werden segmentweise verteilt
- Kundenspezifische Artikelsatz-Vorlagen vorhanden (speichern/anwenden)
- Schnellreferenz fuer Artikelauswahl vorhanden (z. B. `1,4,7`)
- RE-Filter vorhanden (Alle RE / Nur ohne RE-x / Nur mit RE-x) mit Standard "Nur ohne RE-x"
- Exportsteuerung vorhanden:
  - Belegtyp Angebot/Rechnung
  - Exportziel Draft/Finalisieren
- Standard-Belegtitel wird je Gruppe automatisch als `Angebot - <Projekt>` bzw. `Rechnung - <Projekt>` erzeugt
- Regeloptionen im Angebots-/Rechnungsdialog vorhanden:
  - Weiterfahrt-Zuordnung (Tag 1 / Tag 2)
  - Mehrtagespauschale-Zuordnung (Tag 1 / Tag 2)
- PDF/Link-Flow nach Export: Button "In Lexware öffnen" im Erfolgs-Dialog öffnet erstellte Belege im Browser
  - konfigurierbar üeber `LEXWARE_WEB_URL_TEMPLATE` (z. B. `https://app.lexoffice.de/vouchers/{id}`)
  - Fallback: resourceUri direkt wenn HTTP-URL, sonst kein Button
- PDF-Download nach Export: Automatischer Download in konfiguriertes Verzeichnis
  - aktivierbar per `LEXWARE_PDF_DOWNLOAD_ENABLED=true`
  - Zielverzeichnis via `LEXWARE_PDF_DOWNLOADS_DIRECTORY` (z. B. `C:\Rechnungen`)
  - Dateiname automatisch generiert aus Datum, Kunde und Beleg-ID
- Spalten in der Haupt-Tabelle können durch Drag-and-Drop verschoben werden
  - Spaltenanordnung wird in der Sitzung gespeichert und wiederhergestellt

---

# 1. Ziel dieses Dokuments

Dieses Dokument beschreibt ausschließlich den **aktuellen Ist-Stand der vorhandenen GUI**.

Es dient dazu:
- bei späteren Sitzungen schnell den GUI-Stand zu verstehen
- Doppelarbeit zu vermeiden
- vorhandene Funktionen klar von noch fehlenden Rechnungsfunktionen zu trennen

---

# 2. Allgemeine Einordnung

Die GUI ist **bereits deutlich mehr als ein Prototyp**.

Sie ist aktuell eine funktionierende Desktop-Oberfläche für:
- Sichtung von Termin-/Einsatzgruppen
- manuelle Statusbearbeitung
- Freigabe-/Prüfworkflow
- Suche, Filterung und Export
- Speichern/Laden von Arbeitsständen

Die GUI ist damit eine **arbeitsfähige Basis**, auf der der Rechnungs-MVP aufbauen soll.

---

# 3. Technischer Einstiegspunkt

## Hauptfenster
Vorhanden:
- `gui/main_window.py`

## Erstellung
Das Hauptfenster wird in `app/bootstrap.py` erzeugt und mit folgenden Komponenten versorgt:
- `ConfigLoader`
- `ExcelTerminImporter`
- `ContactsCsvImporter`
- `EmployeeBlockExtractor`
- `BlockClassificationService`
- `ProposalBuilderService`
- `GroupingService`
- `InvoiceProposalMapperService`
- `LexwareDraftExportService`

---

# 4. Aktuelle Hauptstruktur der GUI

Die GUI besteht aktuell im Wesentlichen aus:

## 4.1 Oberer Aktionsbereich
Enthält Buttons für:
- Datei öffnen
- Projekt laden
- Projekt speichern
- Sitzung laden
- Sitzung speichern
- CSV exportieren
- JSON exportieren
- Angebot/Rechnung bearbeiten (separates Dialogfenster)
- Lexware exportieren

Enthält zusätzlich:
- Mandantenauswahl (Dropdown, geladen aus `config/mandants.json`)
- Belegtyp-Auswahl (Angebot/Rechnung)
- Exportziel-Auswahl (Draft/Finalisieren)

## 4.2 Filterbereich
Enthält:
- Filter für Automatikstatus
- Filter für manuellen Status
- Filter für geändert / ungeändert
- Filter für RE-x (mit/ohne erledigt-Markierung)
- Buttons:
  - nur offene anzeigen
  - alle manuellen Status anzeigen
- Suchfeld

## 4.3 Aktionsbereich für Statusänderungen
Enthält:
- Freigeben
- Prüfen
- Ignorieren
- Rückgängig

## 4.4 Aktionsbereich für Mehrfachauswahl
Enthält:
- Auswahl freigeben
- Auswahl prüfen
- Auswahl ignorieren
- Auswahl auf offen

## 4.5 Aktionsbereich für sichtbare Gruppen
Enthält:
- alle sichtbaren freigeben
- alle sichtbaren prüfen
- alle sichtbaren ignorieren
- alle sichtbaren auf offen

## 4.6 Zusammenfassungsbereich
Zeigt:
- sichtbar
- ausgewählt
- offen
- freigegeben
- prüfen
- ignorieren
- Prüffälle

## 4.7 Haupttabelle
Zeigt die Gruppenliste

## 4.8 Rechter Detailbereich
Enthält:
- Detailansicht
- Notizfeld
- Änderungsverlauf
- kompakte Draft-Steuerung inkl. Vorschau

Zusätzlich vorhanden:
- separates Angebots-/Rechnungsdialogfenster
  - Belegtitel, Einleitung, Nachbemerkung, Zahlungsziel
  - lokale Vorlagen (Mandantenkonfiguration)
  - Lexware-API Vorlagen
  - kundenbezogener Vorlagenfilter (optional nur kundenspezifisch)
  - Fahrtkostenmodus pro Rechnung
  - Fahrtstunden, KM, Stundensatz, KM-Satz (editierbar)
  - automatische KM-Berechnung (Mandantenadresse -> Einsatzadresse)

Zusätzlich im Sammel-Export vorhanden:
- Blockierung bei Gruppen mit Validierungsfehlern
- explizite Export-Bestaetigung bei Warnungen
- explizite Export-Bestaetigung bei fehlender Geokodierung
- Vorschau je Gruppe inkl. Segmenttext (Route, km, h)
- Segmentrollen in der Vorschau:
  - Erste Rechnung (Anfahrt)
  - Zwischenrechnung
  - Letzte Rechnung (inkl. Rueckfahrt)

## 4.9 Mandantenverhalten (neu)

Vorhanden:
- aktiver Mandant wird im GUI-Zustand gehalten
- Kontakte werden mandantenabhängig geladen
- Mandantenwechsel löst Kunden-Re-Matching für alle Gruppen aus
- aktiver Mandant wird in Sitzungsdatei gespeichert/geladen

---

# 5. Aktuelle Tabellenspalten

Die Tabelle enthält aktuell diese Spalten:

1. Symbol
2. Datum
3. KW
4. Kunde
5. Kundenmatch
6. Projekt
7. Mitarbeiter
8. Status
9. Automatikstatus
10. Validierung
11. RE
12. Adresse
13. Geändert
14. Notiz

---

# 6. Aktuelle Tabellenfunktionen

Vorhanden:
- Zeilenselektion
- Mehrfachauswahl
- Sortierung über Header-Klick
- Alternating row colors
- nicht editierbare Tabellenzellen
- Statussymbol in Spalte 1
- farbliche Markierung je nach Status

---

# 7. Aktuelle Statuslogik in der GUI

## 7.1 Manueller Status
Unterstützte Werte:
- offen
- freigegeben
- pruefen
- ignorieren

## 7.2 Automatischer Gruppenstatus
Unterstützte Anzeige:
- einsatz
- prueffall
- unbekannt

## 7.3 Sichtbarer kombinierter Status
Die GUI zeigt aktuell sinnvoll kombinierte Zustände:
- Offen
- Freigegeben
- Prüfen
- Ignorieren
- Prüffall

---

# 8. Statussymbole

Aktuell verwendet:
- `✓` = freigegeben
- `?` = prüfen
- `–` = ignorieren
- `!` = Prüffall
- leer = offen / sonst

---

# 9. Aktuelle Filterfunktionen

## 9.1 Automatikstatus-Filter
Optionen:
- Alle
- Nur Einsätze
- Nur Prüffälle

## 9.2 Manueller Status-Filter
Optionen:
- Alle
- Offen
- Freigegeben
- Prüfen
- Ignorieren

## 9.3 Änderungsfilter
Optionen:
- Alle
- Nur geänderte
- Nur ungeänderte

## 9.4 Suche
Freitextsuche über u. a.:
- Kunde
- Projekt
- Mitarbeiter
- Adresse
- Ansprechpartner
- Auftrag
- Bemerkungen
- Status
- RE
- manuelle Notiz

---

# 10. Detailansicht

Bei Auswahl einer einzelnen Gruppe zeigt die Detailansicht aktuell u. a.:
- manueller Status
- manuelle Notiz
- Validierungsstatus (OK/Warnung/Blockiert)
- Validierungsmeldungen (Error/Warning/Info)
- Positionsanzahl und Positionsvorschau
- Fahrtkostenmodus und berechnete Fahrtkostenwerte
- Status
- automatischer Status
- Datum
- KW
- Kunde
- Projekt
- Adresse
- Ansprechpartner
- Auftrag
- Bemerkungen
- Mitarbeiter
- RE
- Änderungszeit
- Klassifikationsgründe
- Einträge der Gruppe

Bei Mehrfachauswahl:
- Zusammenfassung der ausgewählten Gruppen

---

# 11. Notizfunktion

Vorhanden:
- manuelle Notiz pro Gruppe
- Notiz speichern
- Notiz wird persistiert
- Notizänderung ist undo-fähig
- Notiz fließt in Suche und Export ein

---

# 12. Änderungsverlauf

Vorhanden:
- Log-Feld rechts unten
- Sitzungsverlauf wird angezeigt
- Aktionen werden protokolliert, z. B.:
  - Datei geladen
  - Projekt gespeichert
  - Projekt geladen
  - Sitzung gespeichert
  - Sitzung geladen
  - Einzelaktion
  - Auswahlaktion
  - Export
  - Rückgängig
  - Notiz gespeichert
  - Details kopiert

---

# 13. Auswahl- und Mehrfachaktionslogik

Vorhanden:
- Mehrfachauswahl in der Tabelle
- Kontextmenü
- Auswahlaktionen per Buttons
- Auswahlaktionen per Kontextmenü
- Bulk-Aktionen für alle sichtbaren Gruppen
- Undo für letzte Aktion

Hinweis:
Ein früheres Rechtsklickproblem bei Mehrfachauswahl wurde bereits behandelt und gilt laut letztem Stand als behoben.

---

# 14. Tastaturkürzel

Vorhanden:
- `F` = freigeben
- `P` = prüfen
- `I` = ignorieren
- `O` = offen
- `Ctrl+Z` = rückgängig

Mit Schutz:
- keine Statusaktion, wenn Texteingabefeld fokussiert ist

---

# 15. Exportfunktionen

## Vorhanden
- CSV-Export der sichtbaren Gruppen
- JSON-Export der sichtbaren Gruppen

## Aktuell exportierte Felder
u. a.:
- manueller Status
- manuelle Notiz
- Status
- Automatikstatus
- Datum
- KW
- Kunde
- Projekt
- Adresse
- Ansprechpartner
- Auftrag
- Bemerkungen
- Mitarbeiter
- RE
- geändert
- Klassifikationsgründe
- Einträge

Wichtiger Hinweis:
Dies ist aktuell noch **kein Lexware-Rechnungsexport**, sondern ein Gruppen-/Vorschlagsexport.

---

# 16. Speichern und Laden

## 16.1 Projektdatei
Vorhanden:
- Projekt speichern
- Projekt laden

Enthält:
- `source_file`
- manuelle Status
- manuelle Notizen

## 16.2 Sitzung
Vorhanden:
- Sitzung speichern
- Sitzung laden

Enthält:
- `source_file`
- Gruppenstatusdaten
- manuelle Notizen
- Änderungszeit
- Änderungsverlauf

## 16.3 Statusdatei neben Quelldatei
Vorhanden:
- `.status.json` wird pro Quelldatei verwendet
- enthält manuelle Status und Notizen

---

# 17. Änderungsmarkierung

Vorhanden:
- Spalte `Geändert`
- Zeitstempel `HH:MM:SS`
- wird bei Status-/Notizänderungen gesetzt
- änderungsbezogene Filter vorhanden

---

# 18. Aktuelle Datenbasis in der GUI

Die GUI arbeitet aktuell bereits mit Gruppenfeldern wie:
- `datum`
- `kw`
- `kunde_roh`
- `projekt_roh`
- `adresse_roh`
- `ansprechpartner_roh`
- `auftrag_roh`
- `bemerkungen_roh`
- `mitarbeiter_liste`
- `re_roh_liste`
- `gruppenstatus`
- `klassifikationsgruende`
- `eintraege`
- `manueller_status`
- `manuelle_notiz`
- `_last_changed_at`

Das ist wichtig, weil die GUI damit bereits auf einer fachlich brauchbaren Gruppenstruktur arbeitet.

---

# 19. Was die GUI aktuell **noch nicht** kann

Noch nicht sichtbar / nicht umgesetzt im gezeigten Stand:

- Anzeige von Mandantenlogo / Firmenadresse als visuelles Branding
- Rechnungsadresse als editierbare Rechnungszieladresse
- Rechnungsname / Belegtitel Lexware
- Kundenreferenz / Bestellnummer
- Exportvalidierung für Rechnungsdaten
- Final-/PDF-Optionen

Bereits vorhanden:
- Lexware Draft Export direkt aus der GUI
- Duplikat-Schutz gegen erneuten Export bereits exportierter Gruppen
- Mandantenauswahl inkl. mandantenabhängigem Kunden-/Artikelkontext
- Kunden-Matching gegen CSV-Stamm
- Artikelauswahl gegen CSV-Stamm inkl. robuster CSV-Import-Fallbacks
- Fahrtkostenberechnung über Routing mit Geocoding-/Koordinaten-Fallback
- Zahlungsziel, Einleitung, Nachbemerkung und Belegtitel im Exportfluss

---

# 20. Wichtigste Bedeutung für die Weiterentwicklung

Die bestehende GUI muss **nicht ersetzt**, sondern **erweitert** werden.

Der nächste große Schritt ist:
- aus der bisherigen Gruppen-/Freigabeansicht
- einen echten Rechnungseditor zu machen

mit:
- Mandant
- Kunde
- Positionen
- Rechnungsdaten
- Validierung
- Draft-Export

---

# 21. Zusammenfassung

## Aktueller Stand
Die GUI ist bereits ein:
> **funktionierendes Prüf-, Freigabe- und Bearbeitungstool für Einsatz-/Vorschlagsgruppen**

## Bedeutung für das Projekt
Das ist eine sehr gute Basis für den Rechnungs-MVP, weil bereits vorhanden sind:
- Übersicht
- Filter
- Detailansicht
- Statuslogik
- Persistenz
- Verlauf
- Exportgrundlagen

## Nächster Schritt
Erster Schritt in der nächsten Sitzung:
- aktuellen Feature-Branch abschließen und nach `main` mergen
- danach neue `feature/...`-Branch erstellen und dort die nächsten GUI-Erweiterungen umsetzen

---