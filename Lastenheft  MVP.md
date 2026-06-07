# LASTENHEFT / MVP
## Rechnungstool für Lexware-Rechnungsentwürfe

Stand: 2026-06-06  
Status: Konsolidierte MVP-Fassung

---

# 1. Ziel

Es soll ein internes Desktop-Tool erstellt bzw. weiterentwickelt werden, das aus einer bestehenden Terminplanungsdatei automatisch **Rechnungsvorschläge** erzeugt, diese in einer GUI bearbeitbar macht und anschließend als **Lexware-Rechnungsentwurf (Draft)** exportiert.

Das Tool soll den bisherigen manuellen Prozess deutlich vereinfachen und dabei die bestehende Terminplanung respektieren.

---

# 2. Hauptziel des MVP

Die erste produktiv nutzbare Version muss:

1. Terminplanung einlesen  
2. abrechnungsrelevante Einsätze erkennen  
3. Rechnungsvorschläge bilden  
4. diese Vorschläge in einer GUI bearbeiten lassen  
5. nach Prüfung als **Draft** in Lexware anlegen

---

# 3. Nicht-Ziele des MVP

Nicht Bestandteil des MVP:

- finale Rechnung direkt erzeugen
- PDF automatisch herunterladen oder öffnen
- Angebote automatisch in Rechnungen überführen
- komplexe Rundreiseautomatik
- Vorlagen-/Favoritensystem
- vollständiger Excel-Lexware-Abgleich
- automatisches Schreiben in die RE-Spalte

Diese Punkte sind für spätere Versionen vorgemerkt.

---

# 4. Datenquellen

## 4.1 Termin- und Einsatzdaten
Die operativen Rechnungs-Rohdaten kommen aus der **Termin-Excel**:

- KW
- Datum
- Wochentag
- Mitarbeiter
- Kunde
- Projekt
- Adresse
- Ansprechpartner
- Auftrag
- Bemerkungen
- RE-Status

## 4.2 Kundenstammdaten
Mandantenbezogene CSV-Dateien aus Lexware:
- `contacts.csv`

## 4.3 Artikeldaten
Mandantenbezogene CSV-Dateien aus Lexware:
- `produkte_services.csv`

## 4.4 Konfiguration
Mehrere JSON-Konfigurationsdateien:
- Mandanten
- Pfade
- Excel-Mapping
- Validierungsregeln
- Defaultwerte

---

# 5. Termin-Excel bleibt read only

Grundregel:

## `termine.xlsx` wird im MVP nicht beschrieben.

Die Datei darf:
- gelesen
- analysiert
- intern verarbeitet

werden, aber nicht geändert.

Das betrifft insbesondere:
- RE-Spalten
- Inhalte
- Formatierungen
- Farben
- Markierungen

---

# 6. Backup-Regel für spätere Excel-Schreibzugriffe

Sobald später Excel beschrieben werden soll, gilt:

Vor jedem Schreibzugriff wird ein Backup erstellt:

```text
backups/YYYY-MM-DD_HHMMSS_termine.xlsx
```

Beispiel:
```text
backups/2026-06-06_154500_termine.xlsx
```

---

# 7. Mandanten / Firmen

Es gibt zwei abrechnende Firmen:

## 7.1 Mandant A
**G.E.S. Energietechnik GmbH**  
Ferchlipp 16  
39615 Altmärkische Wische

## 7.2 Mandant B
**G.E.S. Power Service GmbH**  
Ferchlipp 16  
39615 Altmärkische Wische

Wichtige Regel:
- Der Benutzer wählt in der GUI, für **welchen Mandanten** der Vorschlag gilt.
- Erst danach sind Kunden- und Artikelzuordnung eindeutig.

---

# 8. Lexware-Ziel

Das Zielobjekt des MVP ist:

## **Lexware-Rechnungsentwurf (Draft)**

Nicht Angebot, nicht finale Rechnung.

Die technische Machbarkeit ist bereits nachgewiesen:
- Lesen aus Lexware funktioniert
- Draft-Rechnungen anlegen funktioniert

---

# 9. Struktur der Termin-Excel

## 9.1 Aktuelle Struktur
Die Termin-Excel enthält aktuell **7 wiederholte Mitarbeiterblöcke**.

Pro Mitarbeiterblock existieren sinngemäß Felder wie:
- KW
- Datum
- Wochentag
- Mitarbeitername
- KundeX
- ProjektX
- Adresse
- Ansprechpartner
- Auftrag
- Bemerkungen
- Bittest?
- SLPX
- ESWX
- DPL
- REX

## 9.2 Wichtige Regel
Die Anwendung soll mit dieser bestehenden Struktur arbeiten können.

## 9.3 Interne Verarbeitung
Die breite Excel-Struktur wird beim Import in eine **normierte interne Zeilenstruktur** umgewandelt.

Aus einer Excel-Zeile können intern mehrere abrechnungsrelevante Einträge entstehen.

---

# 10. RE-Spalte

Die RE-Spalte wird im MVP **nicht beschrieben**, aber als Statussignal berücksichtigt.

## Vorläufige Regel:
- `RE = x` → standardmäßig nicht mehr offen
- leer → potenziell offen

RE ist im MVP:
- ein Hinweis
- ein Filterkriterium
- ein Schutz gegen Doppelvorschläge

---

# 11. Importfilter

Das Tool soll nicht immer stumpf alles verarbeiten.

## Unterstützte Filter im MVP:
- alle Termine
- nur eine KW
- KW-Bereich
- nur offene
- **KW/KW-Bereich UND nur offene**

Beispiel:
- `KW 26`
- `KW 26–27`
- `KW 26 und nur offene`

---

# 12. Ausblendelogik

Vergangene und vollständig erledigte Daten dürfen in der **Standardansicht** ausgeblendet werden.

Wichtige Regel:
- nur ausblenden
- nicht löschen
- jederzeit wieder einblendbar

Eine vergangene KW darf nur dann automatisch ausgeblendet werden, wenn für **alle relevanten Mitarbeiter-/RE-Blöcke** in dieser KW keine offenen Rechnungsfälle mehr bestehen.

---

# 13. Klassifikation der Einträge

Nicht jeder gefüllte Block ist ein abrechnungsrelevanter Einsatz.

Jeder importierte Block wird klassifiziert als z. B.:

- `einsatz`
- `frei`
- `krank`
- `urlaub`
- `feiertag`
- `intern`
- `hinweis`
- `prueffall`

Nur `einsatz` fließt standardmäßig in die Vorschlagsbildung ein.  
`prueffall` bleibt sichtbar und muss manuell geprüft werden.

---

# 14. Gruppierungslogik

## 14.1 Ziel
Aus einzelnen abrechnungsrelevanten Einträgen werden **Einsatzblöcke** gebildet.

## 14.2 Startregel für MVP
Automatisch zusammenfassen nur wenn:
- Kunde gleich
- Projekt gleich
- zeitlich zusammenhängend / direkt benachbart
- keine widersprüchlichen Statusmerkmale

## 14.3 Wichtige Regel
Lieber konservativ gruppieren:
- eher zwei Vorschläge als ein falscher großer Vorschlag

## 14.4 Mitarbeiter
Mehrere Mitarbeiter dürfen Teil desselben Einsatzblocks sein.

Die Mitarbeiter müssen später im Vorschlag sichtbar sein.

---

# 15. Rechnungsvorschlag

Aus einem Einsatzblock entsteht im MVP in der Regel **ein Rechnungsvorschlag**.

Ein Vorschlag enthält mindestens:
- Mandant
- Kunde roh
- Kunde zugeordnet
- Kundennummer
- Projektname
- Rechnungsname
- Belegtitel Lexware
- Zeitraum
- beteiligte Mitarbeiter
- Rechnungsadresse
- Positionen
- Zahlungsziel
- Status / Validierung / Exportstatus

---

# 16. Kunde vs. Projekt

## Kunde
- Rechnungsempfänger
- bestimmt Kundenzuordnung / Kundennummer

## Projekt
- Rechnungsbezug
- Grundlage für Rechnungsname
- wichtig für Gruppierung
- wichtig für spätere Angebotslogik
- wichtig für Fahrtkostenlogik

---

# 17. Belegtitel in Lexware

Das Lexware-Feld **Belegtitel** ist hart auf **25 Zeichen** begrenzt.

Wichtig:
- das Wort **„Rechnung“** muss enthalten bleiben

Deshalb gibt es zwei Felder:

## intern
- `rechnungsname_lang`

## Exportfeld
- `belegtitel_lexware`

`belegtitel_lexware` muss:
- gesetzt sein
- max. 25 Zeichen lang sein

---

# 18. Positionen

Ein Rechnungsvorschlag kann **mehrere Positionen** enthalten.

Jede Position enthält mindestens:
- Bezeichnung
- Menge
- Einheit
- Einzelpreis netto
- Steuer / Steuersatz
- Gesamtpreis netto

Artikelnummern sind im MVP:
- intern optional
- nicht das zentrale Bedienfeld
- eher technische Zusatzinfo

---

# 19. Artikelauswahl

Artikel kommen mandantenbezogen aus `produkte_services.csv`.

Im MVP:
- manuelle Auswahl in der GUI
- mehrere Positionen pro Vorschlag
- Preise aus Artikelstamm vorbelegen
- Werte bei Bedarf anpassbar

---

# 20. Kundenzuordnung

Kunden werden mandantenbezogen gegen `contacts.csv` gemappt.

Ergebniszustände:
- eindeutig
- mehrdeutig
- nicht gefunden
- manuell zugeordnet

Export nach Lexware nur mit gültiger Kundenzuordnung.

---

# 21. Rechnungsadresse

Die Rechnungsadresse:
- wird aus dem Kundenstamm vorgeschlagen
- kann aber abweichen
- muss in der GUI editierbar sein

Mindestfelder:
- Name
- Straße
- PLZ
- Ort
- Land

---

# 22. Kundenreferenz / Bestellnummer

Es muss ein Feld geben für z. B.:
- Bestellnummer des Kunden
- Projektnummer des Kunden
- Referenztext

Empfohlene GUI-Beschriftung:
**„Bestellnr. / Projektnr. Kunde“**

---

# 23. Zahlungsziel

Standard:
- **14 Tage netto**

Aber:
- editierbar
- je Vorschlag sichtbar
- Pflicht vor Export

---

# 24. Fahrtkosten

Im MVP nur in einfacher, aber sauberer Form.

Wichtige Regel:
Fahrtkosten dürfen **nicht doppelt** abgerechnet werden.

Mögliche Varianten:
- Fahrtkosten sind im Leistungsartikel enthalten
- Fahrtkosten werden über separaten Artikel abgerechnet

Nicht zulässig:
- beides gleichzeitig doppelt

---

# 25. Mehrtagespauschale

Im MVP:
- als normale Position nutzbar
- manuelle Zuordnung im Vorschlag

---

# 26. GUI-MVP

Die GUI des MVP muss enthalten:

## 26.1 Hauptansicht
- Vorschlagsliste

## 26.2 Detailansicht
- Mandant
- Kunde
- Projekt / Titel
- Mitarbeiter
- Zeitraum
- Adresse
- Positionen
- Zahlungsziel
- Status / Validierung
- Exportbutton

## 26.3 Branding
Für den gewählten Mandanten sichtbar:
- Logo
- Firmenname
- Firmenadresse

---

# 27. Validierung

Vor Export wird geprüft:

- Zielmandant gewählt
- Kunde zugeordnet
- Kundennummer vorhanden
- Rechnungsadresse vollständig
- Belegtitel gesetzt
- Belegtitel <= 25 Zeichen
- mindestens eine gültige Position
- Preise vollständig
- Zahlungsziel gesetzt
- Zeitraum plausibel

## Exportblocker:
- fehlender Mandant
- fehlender Kunde
- fehlende Kundennummer
- unvollständige Adresse
- fehlender/zu langer Belegtitel
- keine gültige Position
- fehlende Preise
- fehlendes Zahlungsziel

---

# 28. Exportmodus im MVP

## Nur:
- **Draft**

Nicht im MVP:
- Final/Open
- Final + PDF

---

# 29. Spätere Ausbaustufen

Nicht MVP, aber geplant:
- PDF herunterladen
- PDF per Button öffnen
- Final-Export
- Vorlagen
- Favoriten / Schnellcodes
- Angebotsübernahme
- Excel/Lexware-Abgleich
- RE automatisch schreiben
- komplexe Fahrt-/Rundreise-Logik

---

# 30. MVP-Erfolgskriterien

Das MVP gilt als erfolgreich, wenn folgende Kette funktioniert:

1. `termine.xlsx` einlesen
2. 7 Mitarbeiterblöcke normalisieren
3. offene Einsätze erkennen
4. nach KW / offen filtern
5. Rechnungsvorschläge bilden
6. Mandant und Kunde zuordnen
7. Positionen pflegen
8. Validierung durchführen
9. als Lexware-Draft exportieren

---

# 31. Wichtiger Hinweis für späteren Codelstart

Vor dem eigentlichen Implementierungsstart soll noch **eine gebündelte Liste aller sinnvollen Excel-Anpassungen** erstellt werden, damit die Datei nur einmal sauber angepasst werden muss.

---