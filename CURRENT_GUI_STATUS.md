# CURRENT GUI STATUS
## Aktueller Stand der vorhandenen GUI

Stand: 2026-06-23
Letztes Update: 2026-06-23

Kurzstatistik:
- Teststand: 112/112 Tests gruen (`pytest -q`)
- Hauptfenster startet in normaler Arbeitsgroesse (kein Vollbild-Start)
- Tabellenliste wurde vergroessert; untere Editorflaechen wurden komprimiert
- Sortierung fuer Mitarbeiter wurde verbessert (sekundaer nach Datum)
- Tour-Filter vorhanden (`Alle`, `Eintagestouren`, `Mehrtagestouren`)
- Angebots-/Rechnungsdialog unterscheidet Texte dynamisch nach Belegtyp
- Zahlungsbedingungen als Auswahl vorhanden, inkl. Anzeige Faelligkeitsdatum
- Artikeltitel und Artikelkommentar sind pro Gruppe editierbar und werden uebernommen
- Preisfeld erlaubt manuelle Eingabe robust (inkl. deutschem Dezimaltrennzeichen)
- Rechnungsvorschau vor Export vorhanden
- Kundenspezifische Defaults werden nach manuellem Loeschen nicht mehr ungefragt neu gesetzt
- PDF-Zielordner wird in der GUI angezeigt; Button zum Oeffnen vorhanden
- "In Lexware oeffnen" nur bei gesetzter `LEXWARE_WEB_URL_TEMPLATE`

---

# 1. Hauptbereiche der GUI

Vorhanden:
- Oberer Aktionsbereich (Datei, Projekt/Sitzung, Export, Bearbeitung)
- Filterbereich (Status, RE, Suche, Tourenfilter)
- Haupttabelle mit Gruppenliste
- Rechter Detail-/Bearbeitungsbereich
- Separater Angebots-/Rechnungsdialog

---

# 2. Exportrelevante GUI-Funktionen

Vorhanden:
- Belegtyp-Auswahl (`Angebot`/`Rechnung`)
- Exportziel-Auswahl (`Draft`/`Finalisieren`)
- Exportblockierung bei harten Validierungsfehlern
- Bestaetigungsdialoge bei Warnungen/fehlender Geokodierung
- Erfolgsdialog mit optionalem Lexware-Link
- PDF-Download nach Export (bei aktivierter ENV-Konfiguration)
- Rechnungsvorschau aus dem realen Payload

---

# 3. Zustand und Persistenz

Vorhanden:
- Projekt-/Sitzungsdateien mit Wiederherstellung der Bearbeitung
- Persistenz fuer kundenspezifische Artikelsaetze und relevante Dialogwerte
- Status-/Aenderungslogik inkl. Undo fuer manuelle Bearbeitung

---

# 4. Bekannte Restthemen (GUI)

- Exporthistorie pro Gruppe noch transparenter darstellen
- Optionales Titel-Template-Feld fuer wiederkehrende Faelle
- Optionales Feld fuer explizit abweichende Rechnungsadresse
