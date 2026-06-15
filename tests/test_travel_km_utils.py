from unittest.mock import patch


def _window_without_init():
    from gui.main_window import MainWindow

    with patch("gui.main_window.QApplication"):
        with patch.object(MainWindow, "__init__", lambda x: None):
            return MainWindow()


def test_extract_coordinates_from_decimal_pair():
    window = _window_without_init()

    coords = window._extract_coordinates_from_text("Koordinaten: 50.8328, 11.9062")

    assert coords is not None
    lat, lon = coords
    assert abs(lat - 50.8328) < 0.0001
    assert abs(lon - 11.9062) < 0.0001


def test_extract_coordinates_from_dms_pair():
    window = _window_without_init()

    coords = window._extract_coordinates_from_text("50°49'58.2\"N 11°54'22.3\"E")

    assert coords is not None
    lat, lon = coords
    assert 50.8 < lat < 50.9
    assert 11.8 < lon < 12.0


def test_normalize_address_for_geocoding_removes_noise():
    window = _window_without_init()

    text = window._normalize_address_for_geocoding(
        "Google-Code: RWM4+4FM Lindenkreuz, Koordinaten: 50°49'58.2\"N 11°54'22.3\"E, 07589 Lindenkreuz"
    )

    assert "Google-Code" not in text
    assert "Koordinaten" not in text
    assert "07589 Lindenkreuz" in text


def test_round_up_to_quarter_hour():
    window = _window_without_init()

    assert window._round_up_to_quarter_hour(5 + (10 / 60)) == 5.25
    assert window._round_up_to_quarter_hour(1.0) == 1.0


def test_round_up_km_to_tens():
    window = _window_without_init()

    assert window._round_up_km_to_tens(294.54) == 300.0
    assert window._round_up_km_to_tens(300.0) == 300.0


def test_calculate_travel_km_for_group_uses_round_trip_values():
    window = _window_without_init()
    window.active_mandant_id = "ges_power_service"
    window._mandant_full_address = lambda _mandant_id: "Ferchlipp 16, 39615 Altmärkische Wische"
    window._geocode_address = lambda _address: (50.0, 11.0)
    window._route_metrics = lambda _start, _end: (110.0, 1.25)

    group = {"adresse_roh": "Musterstr. 1, 12345 Beispielstadt"}
    ok = window._calculate_travel_km_for_group(group, show_messages=False)

    assert ok is True
    assert group["travel_km"] == 220.0
    assert group["travel_hours"] == 2.5


def test_calculate_travel_km_for_group_requires_route_duration():
    window = _window_without_init()
    window.active_mandant_id = "ges_power_service"
    window._mandant_full_address = lambda _mandant_id: "Ferchlipp 16, 39615 Altmärkische Wische"
    window._geocode_address = lambda _address: (50.0, 11.0)
    window._route_metrics = lambda _start, _end: (110.0, 0.0)

    group = {"adresse_roh": "Musterstr. 1, 12345 Beispielstadt"}
    ok = window._calculate_travel_km_for_group(group, show_messages=False)

    assert ok is False
    assert "travel_km" not in group
    assert "travel_hours" not in group


def test_roundtrip_distribution_splits_travel_across_projects_same_day():
    window = _window_without_init()
    window.active_mandant_id = "ges_power_service"
    window._mandant_full_address = lambda _mandant_id: "Firma"

    coords_map = {
        "Firma": (50.0, 11.0),
        "Adresse A": (50.1, 11.1),
        "Adresse B": (50.2, 11.2),
    }
    window._geocode_address = lambda address: coords_map.get(address)

    metrics_map = {
        ((50.0, 11.0), (50.1, 11.1)): (20.0, 0.5),
        ((50.1, 11.1), (50.2, 11.2)): (10.0, 0.25),
        ((50.2, 11.2), (50.0, 11.0)): (30.0, 0.75),
    }
    window._route_metrics = lambda start, end: metrics_map.get((start, end))

    groups = [
        {
            "datum": "2026-04-07 08:00:00",
            "kunde_roh": "PowerCorp",
            "projekt_roh": "Projekt A",
            "adresse_roh": "Adresse A",
            "travel_km": 0.0,
            "travel_hours": 0.0,
        },
        {
            "datum": "2026-04-07 11:00:00",
            "kunde_roh": "PowerCorp",
            "projekt_roh": "Projekt B",
            "adresse_roh": "Adresse B",
            "travel_km": 0.0,
            "travel_hours": 0.0,
        },
    ]

    applied = window._apply_roundtrip_distribution_for_groups(groups)

    assert applied == 1
    assert groups[0]["travel_km"] == 20.0
    assert groups[0]["travel_hours"] == 0.5
    assert groups[0]["travel_route_origin"] == "Firma"
    assert groups[0]["travel_route_destination"] == "Adresse A"
    assert groups[0]["travel_segment_role"] == "first_invoice_outbound"

    assert groups[1]["travel_km"] == 40.0
    assert groups[1]["travel_hours"] == 1.0
    assert groups[1]["travel_route_origin"] == "Adresse A"
    assert "Rueckfahrt zur Firma" in groups[1]["travel_route_destination"]
    assert groups[1]["travel_segment_role"] == "last_invoice_with_return"


def test_roundtrip_distribution_does_not_override_existing_manual_values():
    window = _window_without_init()
    window.active_mandant_id = "ges_power_service"
    window._mandant_full_address = lambda _mandant_id: "Firma"
    window._geocode_address = lambda _address: (50.0, 11.0)
    window._route_metrics = lambda _start, _end: (10.0, 0.25)

    groups = [
        {
            "datum": "2026-04-07 08:00:00",
            "kunde_roh": "PowerCorp",
            "projekt_roh": "Projekt A",
            "adresse_roh": "Adresse A",
            "travel_km": 50.0,
            "travel_hours": 1.0,
        },
        {
            "datum": "2026-04-07 11:00:00",
            "kunde_roh": "PowerCorp",
            "projekt_roh": "Projekt B",
            "adresse_roh": "Adresse B",
            "travel_km": 0.0,
            "travel_hours": 0.0,
        },
    ]

    applied = window._apply_roundtrip_distribution_for_groups(groups)

    assert applied == 0
    assert groups[0]["travel_km"] == 50.0
    assert groups[0]["travel_hours"] == 1.0


def test_roundtrip_distribution_forward_assignment_rule_tag_1():
    window = _window_without_init()
    window.active_mandant_id = "ges_power_service"
    window._mandant_full_address = lambda _mandant_id: "Firma"

    coords_map = {
        "Firma": (50.0, 11.0),
        "Adresse A": (50.1, 11.1),
        "Adresse B": (50.2, 11.2),
    }
    window._geocode_address = lambda address: coords_map.get(address)

    metrics_map = {
        ((50.0, 11.0), (50.1, 11.1)): (20.0, 0.5),
        ((50.1, 11.1), (50.2, 11.2)): (10.0, 0.25),
        ((50.2, 11.2), (50.0, 11.0)): (30.0, 0.75),
    }
    window._route_metrics = lambda start, end: metrics_map.get((start, end))

    groups = [
        {
            "datum": "2026-04-07 08:00:00",
            "kunde_roh": "PowerCorp",
            "projekt_roh": "Projekt A",
            "adresse_roh": "Adresse A",
            "travel_forward_assignment_rule": "tag_1",
            "travel_km": 0.0,
            "travel_hours": 0.0,
        },
        {
            "datum": "2026-04-07 11:00:00",
            "kunde_roh": "PowerCorp",
            "projekt_roh": "Projekt B",
            "adresse_roh": "Adresse B",
            "travel_forward_assignment_rule": "tag_1",
            "travel_km": 0.0,
            "travel_hours": 0.0,
        },
    ]

    applied = window._apply_roundtrip_distribution_for_groups(groups)

    assert applied == 1
    # Tag-1-Regel: Weiterfahrt A->B auf erste Rechnung
    assert groups[0]["travel_km"] == 30.0
    assert groups[0]["travel_hours"] == 0.75
    assert groups[1]["travel_km"] == 30.0
    assert groups[1]["travel_hours"] == 0.75
