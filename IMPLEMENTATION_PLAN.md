# IMPLEMENTATION PLAN
## Konkreter Umsetzungsplan für die nächsten Coding-Schritte

Stand: 2026-06-06

---

# 1. Ziel dieses Dokuments

Dieses Dokument beschreibt die **nächsten konkreten Entwicklungsschritte**, um vom aktuellen Ist-Stand des Tools zum definierten Rechnungs-MVP zu kommen.

Es ist bewusst praxisnah gehalten und soll als direkte Arbeitsgrundlage für die Umsetzung dienen.

---

# 2. Ausgangslage

Bereits vorhanden:
- funktionierende GUI
- Import aus CSV/XLSX
- Mitarbeiterblock-Extraktion
- Klassifikation
- Proposal-Kandidaten
- einfache Gruppierung
- Statusworkflow
- Notizen / Verlauf / Speichern / Laden
- Export CSV/JSON

Noch nicht vorhanden:
- mandantenfähiger Rechnungsentwurf
- Kunden-/Artikel-Mapping
- Rechnungspositionen
- Rechnungsvalidierung
- Lexware Draft Export aus GUI

---

# 3. Leitprinzip

Wir bauen **nicht neu**, sondern **erweitern gezielt**.

Wichtig:
- bestehende GUI erhalten
- bestehende Importpipeline weiterverwenden
- Rechnungslogik als nächste Schicht ergänzen
- Risiken früh über klare Datenmodelle und konservative Gruppierung minimieren

---

# 4. Arbeitsblock A – Projektstruktur und Konfiguration vervollständigen

## Ziel
Den aktuellen Stand technisch stabilisieren und für Rechnungslogik vorbereiten.

## Aufgaben
- fehlende Projektordner anlegen:
  - `domain/`
  - `lexware/`
  - `storage/`
  - `tests/`
  - `assets/logos/`
- Konfigurationsdateien anlegen bzw. vervollständigen:
  - `mandants.json`
  - `excel_import.json`
  - `validation.json`
  - `defaults.json`
  - `backup.json`
- Pfadstruktur für Mandanten festlegen:
  - `data/ges_energietechnik/`
  - `data/ges_power_service/`

## Ergebnis
Saubere Grundlage, auf der die nächsten Module aufsetzen können.

---

# 5. Arbeitsblock B – Rechnungsentwurfs-Datenmodell einführen

## Ziel
Ein explizites Rechnungsmodell neben der bestehenden Gruppendarstellung schaffen.

## Neue Objekte
- `InvoiceProposal`
- `InvoicePosition`
- `ValidationMessage`
- `ExportState`
- optional:
  - `CustomerMatchResult`
  - `MandantConfig`

## Aufgaben
- neue Domain-Dateien anlegen
- bestehende Gruppendaten auf diese Strukturen abbilden
- Felder ergänzen für:
  - Mandant
  - Kunde zugeordnet
  - Kundennummer
  - Rechnungsname
  - Belegtitel
  - Kundenreferenz
  - Zahlungsziel
  - Positionen
  - Validierung
  - Exportstatus

## Ergebnis
Das System arbeitet nicht mehr nur mit Einsatzgruppen, sondern mit echten Rechnungsentwurf-Objekten.

---

# 6. Arbeitsblock C – Gruppierungslogik auf Rechnungsblöcke umbauen

## Ziel
Die aktuelle Gruppierung `Datum + Kunde + Projekt` auf eine rechnungstaugliche Logik erweitern.

## Problem heute
Der bestehende `GroupingService` gruppiert eher tagesbezogen.

## Zielzustand
Zusammengehörige Einsätze über mehrere Tage sollen zu einem Einsatzblock / Vorschlag werden.

## Aufgaben
- neue Gruppierungsregel implementieren:
  - gleicher Kunde
  - gleiches Projekt
  - zusammenhängende oder direkt benachbarte Tage
  - mehrere Mitarbeiter möglich
- konservative Gruppierung beibehalten:
  - lieber trennen als falsch zusammenführen
- `prueffall` sichtbar halten

## Ergebnis
Mehrtägige Einsatzblöcke als Grundlage für Rechnungsentwürfe.

---

# 7. Arbeitsblock D – Mandantenlogik einbauen

## Ziel
Jeder Vorschlag bekommt einen abrechnenden Mandanten.

## Aufgaben
- `mandants.json` laden
- Mandantenauswahl in GUI einführen
- Mandantenkopf in GUI ergänzen:
  - Firmenname
  - Adresse
  - Logo
- Mandantenwechsel soll Kunden-/Artikelkontext beeinflussen

## Ergebnis
Das Tool wird mandantenfähig.

---

# 8. Arbeitsblock E – Kundenstammdaten aktiv integrieren

## Ziel
Rechnungsempfänger sauber gegen mandantenbezogene CSV-Stämme mappen.

## Aufgaben
- `ContactsCsvImporter` in `bootstrap.py` integrieren
- Kundenstämme pro Mandant laden
- `CustomerMatcher` bauen
- Matchzustände unterstützen:
  - eindeutig
  - mehrdeutig
  - nicht gefunden
  - manuell zugeordnet

## GUI-Erweiterung
- Kunde roh anzeigen
- zugeordneten Kunden anzeigen
- Kundennummer anzeigen
- Mapping-Status anzeigen

## Ergebnis
Jeder exportfähige Vorschlag kann einem Lexware-Kundenstamm zugeordnet werden.

---

# 9. Arbeitsblock F – Artikeldaten und Positionseditor

## Ziel
Rechnungspositionen im Tool pflegen können.

## Aufgaben
- `ArticlesCsvImporter` in `bootstrap.py` integrieren
- Artikellisten pro Mandant laden
- Positionsmodell einführen
- Positionseditor in GUI ergänzen:
  - Position hinzufügen
  - löschen
  - bearbeiten
  - Preis / Menge / Steuer pflegen

## Ergebnis
Pro Vorschlag können echte Rechnungspositionen gepflegt werden.

---

# 10. Arbeitsblock G – Rechnungsfelder in GUI ergänzen

## Ziel
Die bestehende GUI zum Rechnungseditor erweitern.

## Neue Felder in der Detailansicht
- Zielmandant
- Kunde zugeordnet
- Kundennummer
- Rechnungsname lang
- Belegtitel Lexware
- Kundenreferenz
- Auftrag / Projektnummer Kunde
- Rechnungsadresse
- Zahlungsziel
- Positionen
- Validierungsstatus
- Exportstatus

## Wichtige Regel
Bestehende GUI-Funktionen wie:
- Statusworkflow
- Suche
- Notizen
- Verlauf
- Speichern / Laden
werden nach Möglichkeit beibehalten.

## Ergebnis
Die GUI wird zum Rechnungs-MVP-Editor.

---

# 11. Arbeitsblock H – Validierungslogik

## Ziel
Nur vollständige und plausible Vorschläge exportierbar machen.

## Zu prüfen
- Mandant gesetzt
- Kunde zugeordnet
- Kundennummer vorhanden
- Rechnungsadresse vollständig
- Belegtitel gesetzt und <= 25 Zeichen
- mindestens eine gültige Position
- Preise vollständig
- Zahlungsziel vorhanden

## Umsetzung
- `ValidationService` erweitern
- Feldfehler im GUI sichtbar machen
- Gesamtstatus pro Vorschlag berechnen

## Ergebnis
Klarer Exportstatus:
- fehlerhaft
- warnungen
- exportbereit

---

# 12. Arbeitsblock I – Lexware Draft Export

## Ziel
Rechnungsentwürfe aus der GUI heraus als Draft in Lexware anlegen.

## Aufgaben
- `LexwareClient` oder `LexwareDraftExportService` anlegen
- Proposal -> Lexware-Payload Mapping bauen
- Exportbutton integrieren
- Rückgabe speichern:
  - Lexware-ID
  - Resource-URI
  - Exportzeitpunkt
  - Fehlerstatus
- Mehrfachexporte absichern

## Ergebnis
Erster produktiver End-to-End-Prozess.

---

# 13. Arbeitsblock J – Backup-Service vorbereiten

## Ziel
Spätere Excel-Schreiblogik absichern.

## Im aktuellen MVP
Noch kein aktives Schreiben in Excel nötig.

## Trotzdem vorbereiten
- `BackupService` finalisieren
- Dateinamenschema festziehen
- Fehlerbehandlung definieren

## Ergebnis
Schreibzugriffe sind vorbereitet, ohne das MVP zu blockieren.

---

# 14. Konkrete Reihenfolge der nächsten 5 Coding-Schritte

## Schritt 1
**Konfiguration + Domain-Modelle einführen**
- `mandants.json`
- `validation.json`
- `defaults.json`
- `InvoiceProposal`
- `InvoicePosition`
- `ValidationMessage`
- `ExportState`

## Schritt 2
**Bootstrap erweitern**
- `ContactsCsvImporter` einhängen
- `ArticlesCsvImporter` einhängen
- Mandanten laden

## Schritt 3
**GroupingService rechnungstauglich umbauen**
- mehrtägige Einsatzblöcke
- Mitarbeiterliste über mehrere Tage

## Schritt 4
**GUI-Detailansicht erweitern**
- Mandant
- Kunde
- Rechnungsfelder
- Zahlungsziel
- Positionen

## Schritt 5
**Validation + Draft Export**
- Exportbereitschaft
- Lexware-Payload
- Draft-Export aus GUI

---

# 15. Empfohlener nächster echter Entwicklungsblock

## Sofort beginnen mit:
### **Rechnungsentwurfs-Datenmodell + Gruppierungsumbau**

## Warum?
Weil:
- GUI schon vorhanden ist
- Import schon vorhanden ist
- aber ohne neues Rechnungsmodell und bessere Gruppierung der Rechnungsworkflow nicht sauber anschließt

---

# 16. Was jetzt bewusst noch nicht angefasst werden sollte

Vorläufig zurückstellen:
- Final-Export
- PDF-Download
- Vorlagen / Favoriten
- Angebotsübernahme
- komplexe Fahrtlogik
- Excel/Lexware-Abweichungsprüfung
- RE in Excel schreiben

Diese Themen werden später einfacher, wenn der Rechnungs-MVP-Kern steht.

---

# 17. Definition des MVP-Meilensteins

Der erste echte Meilenstein ist erreicht, wenn:

1. Termin-Excel geladen werden kann  
2. offene Einsätze zu rechnungstauglichen Blöcken gruppiert werden  
3. daraus Rechnungsentwürfe entstehen  
4. Mandant und Kunde zugeordnet werden können  
5. Positionen gepflegt werden können  
6. Validierung greift  
7. ein Vorschlag als Draft in Lexware exportiert werden kann

---

# 18. Wichtiger vorbereitender Hinweis für Implementierungsstart

Vor dem tatsächlichen Umbau der Excel-Datei soll noch **eine gebündelte Liste sinnvoller Excel-Anpassungen** erstellt werden.

Nicht jetzt schrittweise ändern, sondern gesammelt:
- RE-Namen vereinheitlichen
- Blockfeldnamen vereinheitlichen
- sonstige kleine Benennungsoptimierungen

---

# 19. Zusammenfassung

## Vorhandene starke Basis
- GUI
- Import
- Klassifikation
- Kandidatenbildung
- Statusworkflow

## Nächste logische Brücke
- Rechnungsentwurfsmodell
- rechnungstaugliche Gruppierung
- Mandanten-/Kunden-/Artikelintegration
- Positionseditor
- Validierung
- Draft-Export

## Wichtigste unmittelbare Entscheidung
> Als Nächstes **kein weiteres Feintuning der alten GUI**, sondern den **Rechnungsentwurfs-Kern** einbauen.

---