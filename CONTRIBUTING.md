# Entwicklungsworkflow

Stand: 2026-06-14

## Branch-Regeln

- `main` bleibt jederzeit stabil und releasefaehig.
- Neue Arbeit erfolgt immer in einem Feature-Branch.
- Branch-Namen:
  - `feature/<kurze-beschreibung>`
  - `fix/<kurze-beschreibung>`

## Standardablauf

1. Neuen Branch erstellen
   - `git switch -c feature/<name>`
2. Implementieren und lokal testen
3. Committen und pushen
   - `git add -A`
   - `git commit -m "..."`
   - `git push -u origin <branch>`
4. Pull Request auf `main` erstellen
5. Merge erst bei gruener CI und bestandenem GUI-Smoketest

## Pflicht-Checks vor Merge

- CI-Workflow erfolgreich
- Kein Secret im Repo
- GUI-Smoketest lokal erfolgreich
- Export-Duplikat-Schutz geprueft
- Doku aktualisiert (`README.md`, `CURRENT_GUI_STATUS.md`, `IMPLEMENTATION_PLAN.md`) falls Verhalten/Funktionen geaendert wurden

## Doku-Regel

Bei jeder fachlichen oder GUI-relevanten Aenderung gilt:
- Ist-Zustand in den Markdown-Dokumenten auf denselben Stand bringen
- neue Umgebungsvariablen in `README.md` dokumentieren
- offene Punkte in `IMPLEMENTATION_PLAN.md` nachziehen

## Tagesabschluss-Hinweis (2026-06-14)

- Naechster erster Schritt in der naechsten Sitzung:
   - aktuellen Feature-Branch via PR abschliessen
   - nach `main` mergen
   - neue `feature/...`-Branch fuer die weitere Entwicklung starten
