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
