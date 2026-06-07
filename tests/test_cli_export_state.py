import json

from app.cli_export_test import (
    _apply_saved_group_state,
    _build_group_key,
    _is_already_exported,
    _save_group_state,
)


def _group() -> dict:
    return {
        "datum": "2026-04-07",
        "kunde_roh": "Testkunde GmbH",
        "projekt_roh": "Projekt X",
        "manueller_status": "offen",
        "manuelle_notiz": "",
        "lexware_export_status": "",
        "lexware_export_id": "",
        "lexware_exported_at": "",
    }


def test_is_already_exported_true_only_with_status_and_id():
    group = _group()
    group["lexware_export_status"] = "exportiert"
    group["lexware_export_id"] = "abc-123"

    assert _is_already_exported(group) is True


def test_is_already_exported_false_without_id():
    group = _group()
    group["lexware_export_status"] = "exportiert"

    assert _is_already_exported(group) is False


def test_save_and_apply_group_state_roundtrip(tmp_path):
    source_file = str(tmp_path / "Termine.xlsx")
    groups = [_group()]

    groups[0]["lexware_export_status"] = "exportiert"
    groups[0]["lexware_export_id"] = "id-001"
    groups[0]["lexware_exported_at"] = "2026-06-07T21:00:00"
    groups[0]["manuelle_notiz"] = "bereits exportiert"

    _save_group_state(source_file, groups)

    status_file = tmp_path / "Termine.xlsx.status.json"
    assert status_file.exists()

    persisted = json.loads(status_file.read_text(encoding="utf-8"))
    key = _build_group_key(groups[0])
    assert key in persisted

    fresh_groups = [_group()]
    _apply_saved_group_state(source_file, fresh_groups)

    assert fresh_groups[0]["lexware_export_status"] == "exportiert"
    assert fresh_groups[0]["lexware_export_id"] == "id-001"
    assert fresh_groups[0]["manuelle_notiz"] == "bereits exportiert"
