# IMPLEMENTATION PLAN
## Konkreter Umsetzungsplan ab aktuellem Stand

Stand: 2026-06-23
Letztes Update: 2026-06-23

---

# 1. Ziel dieses Dokuments

Dieses Dokument beschreibt die **konkrete Umsetzungsreihenfolge** fuer die naechsten Entwicklungsbloecke nach dem erreichten MVP-Stand.

Es dient als Arbeitsplan fuer technische Umsetzung, Tests und Doku-Sync.

---

# 2. Ausgangslage (heute)

Bereits vorhanden:
- Produktive GUI fuer Sichtung, Bearbeitung und Export
- Lexware-Export (`Angebot`/`Rechnung`, `Draft`/`Finalisieren`)
- Rechnungsvorschau vor Export
- Zahlungsbedingungen-Auswahl inkl. Faelligkeitsanzeige
- Tour-Filter (`Alle`, `Eintagestouren`, `Mehrtagestouren`)
- PDF-Download nach Export und PDF-Ordner-Button in der GUI
- Deterministische Kundenaufloesung (Kundennummer priorisiert)
- Artikelkommentar/-titel editierbar und exportwirksam
- Teststand: 112/112 Tests gruen

Noch offen (fachlich sinnvoll):
- Bessere Exporthistorie/Nachverfolgung pro Gruppe
- Optionales Titel-Template mit Platzhaltern
- Optional explizit abweichende Rechnungsadresse
- Weitere GUI-Regressionstests fuer sensible Interaktionen

---

# 3. Arbeitsblock A - Exporthistorie transparent machen

## Ziel
Export-Ergebnisse pro Gruppe schneller nachvollziehbar machen.

## Aufgaben
- Exportmetadaten je Gruppe strukturieren (Zeitpunkt, Beleg-ID, Endpoint, Ergebnis)
- Fehler-/Warnungstexte persistieren und in der GUI besser sichtbar machen
- Optional: Filter "zuletzt fehlgeschlagen" pruefen

## Done-Kriterium
- Anwender erkennt ohne Logs, welche Gruppe wann/wie exportiert wurde und warum ein Export ggf. fehlschlug.

---

# 4. Arbeitsblock B - Dialog-Produktivitaet verbessern

## Ziel
Weniger manuelle Wiederholung bei wiederkehrenden Rechnungsfaellen.

## Aufgaben
- Optionales Titel-Template-Feld mit Platzhaltern (`{typ}`, `{projekt}`, `{datum}`)
- Optionales Feld fuer explizit abweichende Rechnungsadresse
- UX-Feinschliff fuer Artikeltextpflege (schnelleres Speichern/Feedback)

## Done-Kriterium
- Wiederkehrende Faelle sind mit weniger Klicks bearbeitbar, ohne Exportlogik zu destabilisieren.

---

# 5. Arbeitsblock C - Test- und Betriebsstabilitaet

## Ziel
GUI- und Exportverhalten robuster gegen Regressionen machen.

## Aufgaben
- Tests fuer neue GUI-Interaktionen erweitern (Filter, Splitter, Editor-Sync)
- Tests fuer Export-Edgecases erweitern (fehlende ENV, Kundenkollisionen, PDFs)
- Logging fuer Exportfehler standardisieren (ohne Secrets)

## Done-Kriterium
- Kritische Flows sind automatisiert abgesichert und Fehler im Betrieb schneller analysierbar.

---

# 6. Arbeitsmodus pro Änderung

1. Feature in kleinem, klar abgegrenztem Block umsetzen
2. Tests ausfuehren (`pytest -q`)
3. Doku synchronisieren (`README.md`, `CURRENT_GUI_STATUS.md`, `PROJECT_STATUS.md.txt`, `NEXT_STEPS.md.txt`)
4. Commit mit praeziser Message
5. Push / PR nach Teamprozess
