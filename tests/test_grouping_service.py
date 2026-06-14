from services.grouping_service import GroupingService


def _candidate(
    datum: str,
    kunde: str = "Kunde A",
    projekt: str = "Projekt A",
    mitarbeiter: str = "Max",
    klassifikation: str = "einsatz",
) -> dict:
    return {
        "datum": datum,
        "kw": "23",
        "kunde_roh": kunde,
        "projekt_roh": projekt,
        "adresse_roh": "Musterweg 1",
        "ansprechpartner_roh": "Herr Test",
        "auftrag_roh": "A-1",
        "bemerkungen_roh": "",
        "re_roh": "",
        "mitarbeiter": mitarbeiter,
        "klassifikation": klassifikation,
        "klassifikationsgrund": "test",
    }


def test_groups_contiguous_days_for_same_customer_and_project():
    service = GroupingService()
    candidates = [
        _candidate("2026-06-01", mitarbeiter="Max"),
        _candidate("2026-06-02", mitarbeiter="Eva"),
    ]

    grouped = service.group_candidates(candidates)

    assert len(grouped) == 1
    assert grouped[0]["datum"] == "2026-06-01"
    assert grouped[0]["zeitraum_von"] == "2026-06-01"
    assert grouped[0]["zeitraum_bis"] == "2026-06-02"
    assert grouped[0]["mitarbeiter_liste"] == ["Eva", "Max"]


def test_splits_group_when_day_gap_is_larger_than_one():
    service = GroupingService()
    candidates = [
        _candidate("2026-06-01"),
        _candidate("2026-06-03"),
    ]

    grouped = service.group_candidates(candidates)

    assert len(grouped) == 2
    assert grouped[0]["zeitraum_bis"] == "2026-06-01"
    assert grouped[1]["zeitraum_von"] == "2026-06-03"


def test_splits_group_when_classification_changes():
    service = GroupingService()
    candidates = [
        _candidate("2026-06-01", klassifikation="einsatz"),
        _candidate("2026-06-02", klassifikation="prueffall"),
    ]

    grouped = service.group_candidates(candidates)

    assert len(grouped) == 2
    assert grouped[0]["gruppenstatus"] == "einsatz"
    assert grouped[1]["gruppenstatus"] == "prueffall"
