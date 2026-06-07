import argparse
import json
from datetime import datetime
from pathlib import Path

from app.config_loader import ConfigLoader
from app.env_loader import EnvLoader
from importer.employee_block_extractor import EmployeeBlockExtractor
from importer.excel_termin_importer import ExcelTerminImporter
from services.block_classification_service import BlockClassificationService
from services.grouping_service import GroupingService
from services.lexware_draft_export_service import LexwareDraftExportService
from services.proposal_builder_service import ProposalBuilderService


def _build_group_key(group: dict) -> str:
    return "||".join(
        [
            str(group.get("datum", "")).strip(),
            str(group.get("kunde_roh", "")).strip().lower(),
            str(group.get("projekt_roh", "")).strip().lower(),
        ]
    )


def _is_already_exported(group: dict) -> bool:
    status = str(group.get("lexware_export_status", "")).strip().lower()
    export_id = str(group.get("lexware_export_id", "")).strip()
    return status == "exportiert" and bool(export_id)


def _status_file_path(source_file: str) -> Path:
    return Path(source_file + ".status.json")


def _apply_saved_group_state(source_file: str, groups: list[dict]) -> None:
    status_file = _status_file_path(source_file)
    if not status_file.exists():
        return

    try:
        with open(status_file, "r", encoding="utf-8") as f:
            saved = json.load(f)
    except Exception:
        return

    if not isinstance(saved, dict):
        return

    for group in groups:
        entry = saved.get(_build_group_key(group))
        if not isinstance(entry, dict):
            continue
        group["manueller_status"] = entry.get("manueller_status", group.get("manueller_status", "offen"))
        group["manuelle_notiz"] = entry.get("manuelle_notiz", group.get("manuelle_notiz", ""))
        group["lexware_export_status"] = entry.get("lexware_export_status", group.get("lexware_export_status", ""))
        group["lexware_export_id"] = entry.get("lexware_export_id", group.get("lexware_export_id", ""))
        group["lexware_exported_at"] = entry.get("lexware_exported_at", group.get("lexware_exported_at", ""))


def _save_group_state(source_file: str, groups: list[dict]) -> None:
    status_file = _status_file_path(source_file)

    payload: dict[str, dict] = {}
    for group in groups:
        manual_status = group.get("manueller_status", "offen")
        manual_note = group.get("manuelle_notiz", "")
        export_status = group.get("lexware_export_status", "")
        export_id = group.get("lexware_export_id", "")
        exported_at = group.get("lexware_exported_at", "")

        if manual_status != "offen" or manual_note or export_status or export_id or exported_at:
            payload[_build_group_key(group)] = {
                "manueller_status": manual_status,
                "manuelle_notiz": manual_note,
                "lexware_export_status": export_status,
                "lexware_export_id": export_id,
                "lexware_exported_at": exported_at,
            }

    with open(status_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def _resolve_input_file(path_arg: str) -> str:
    candidate = Path(path_arg)
    if candidate.exists():
        return str(candidate)

    fallbacks = [
        Path("data/Termine.xlsx"),
        Path("data/termine.xlsx"),
    ]
    for path in fallbacks:
        if path.exists():
            return str(path)

    return str(candidate)


def _load_groups(source_file: str) -> list[dict]:
    config_loader = ConfigLoader()
    importer = ExcelTerminImporter()
    extractor = EmployeeBlockExtractor()
    classifier = BlockClassificationService()
    builder = ProposalBuilderService()
    grouping = GroupingService()

    excel_config = config_loader.load_json("excel_import.json")["excel_import"]
    block_configs = excel_config["employee_blocks"]
    sheet_name = excel_config.get("sheet_name")

    rows = importer.load_rows(source_file, sheet_name=sheet_name)

    all_candidates: list[dict] = []
    for row_index in range(1, len(rows)):
        blocks = extractor.extract_blocks_from_row(rows[row_index], block_configs)
        filled = [b for b in blocks if extractor.is_block_meaningfully_filled(b)]
        candidates = builder.build_proposal_candidates(filled, classifier)
        all_candidates.extend(candidates)

    groups = grouping.group_candidates(all_candidates)
    for group in groups:
        group.setdefault("manueller_status", "offen")
        group.setdefault("manuelle_notiz", "")
        group.setdefault("lexware_export_status", "")
        group.setdefault("lexware_export_id", "")
        group.setdefault("lexware_exported_at", "")

    _apply_saved_group_state(source_file, groups)

    return groups


def main() -> int:
    parser = argparse.ArgumentParser(description="Headless Lexware-Draft-Export Test")
    parser.add_argument("--file", default="data/Termine.xlsx", help="Pfad zur Termin-Datei (xlsx/csv)")
    parser.add_argument("--limit", type=int, default=1, help="Anzahl Gruppen für Testexport")
    parser.add_argument("--all", action="store_true", help="Alle offenen Gruppen exportieren")
    parser.add_argument("--include-review", action="store_true", help="Auch prueffall-Gruppen einbeziehen")
    parser.add_argument("--include-exported", action="store_true", help="Bereits exportierte Gruppen nicht ueberspringen")
    parser.add_argument("--dry-run", action="store_true", help="Nur Payload anzeigen, nicht an Lexware senden")
    args = parser.parse_args()

    EnvLoader.load_from_file(".env")

    source_file = _resolve_input_file(args.file)
    if not Path(source_file).exists():
        print(f"Fehler: Quelldatei nicht gefunden: {source_file}")
        return 2

    groups = _load_groups(source_file)
    if not groups:
        print("Keine Gruppen gefunden.")
        return 0

    open_groups = [g for g in groups if g.get("manueller_status", "offen") == "offen"]
    if not args.include_review:
        open_groups = [g for g in open_groups if g.get("gruppenstatus") == "einsatz"]
    if not args.include_exported:
        open_groups = [g for g in open_groups if not _is_already_exported(g)]

    if not open_groups:
        print("Keine passenden offenen Gruppen für Export gefunden.")
        return 0

    selected = open_groups if args.all else open_groups[: max(args.limit, 1)]

    service = LexwareDraftExportService()
    if not args.dry_run and not service.is_configured():
        print("Fehler: Lexware nicht konfiguriert. Bitte .env prüfen.")
        print("Erforderlich: BASE_URL + ACCESS_TOKEN oder Refresh-Flow (CLIENT_ID/CLIENT_SECRET/REFRESH_TOKEN/TOKEN_URL)")
        return 2

    print(f"Quelle: {source_file}")
    print(f"Gefundene Gruppen: {len(groups)} | Exportkandidaten: {len(selected)}")

    ok_count = 0
    fail_count = 0

    for idx, group in enumerate(selected, start=1):
        kunde = group.get("kunde_roh", "")
        projekt = group.get("projekt_roh", "")
        datum = group.get("datum", "")
        print(f"\n[{idx}] {datum} | {kunde} | {projekt}")

        if args.dry_run:
            payload = service._build_payload(group)
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            continue

        result = service.export_group_as_draft(group)
        if result.get("success"):
            ok_count += 1
            response = result.get("response")
            if isinstance(response, dict):
                export_id = response.get("id") or response.get("voucherNumber") or response.get("resourceUri")
            else:
                export_id = ""
            group["lexware_export_status"] = "exportiert"
            group["lexware_export_id"] = str(export_id or "")
            group["lexware_exported_at"] = datetime.now().isoformat(timespec="seconds")
            print(f"OK | HTTP {result.get('status_code')} | ID: {export_id}")
        else:
            fail_count += 1
            group["lexware_export_status"] = "fehler"
            group["lexware_export_id"] = ""
            group["lexware_exported_at"] = ""
            print(f"FEHLER | HTTP {result.get('status_code')} | {result.get('error')}")
            if result.get("response"):
                print(f"Antwort: {result.get('response')}")

    if args.dry_run:
        print("\nDry-run abgeschlossen.")
        return 0

    _save_group_state(source_file, groups)

    print(f"\nErfolgreich: {ok_count} | Fehlgeschlagen: {fail_count}")
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
