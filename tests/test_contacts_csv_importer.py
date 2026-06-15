from importer.contacts_csv_importer import ContactsCsvImporter


def test_contacts_importer_fallback_cp1252(tmp_path):
    content = (
        "Kundennummer;Firmenname;Straße 1;PLZ 1;Ort 1;Land 1\n"
        "10057;GRÜPER Ahlhorn GmbH & Co. KG;Musterweg 1;26197;Ahlhorn;DE\n"
    )
    path = tmp_path / "contacts_cp1252.csv"
    path.write_bytes(content.encode("cp1252"))

    importer = ContactsCsvImporter()
    rows = importer.load(str(path))

    assert len(rows) == 1
    assert rows[0]["Firmenname"] == "GRÜPER Ahlhorn GmbH & Co. KG"
    assert rows[0]["Straße 1"] == "Musterweg 1"
