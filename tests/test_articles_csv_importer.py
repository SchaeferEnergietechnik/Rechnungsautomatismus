from importer.articles_csv_importer import ArticlesCsvImporter


def test_load_articles_csv_with_cp1252_encoding(tmp_path):
    csv_path = tmp_path / "produkte_services.csv"
    content = (
        b'"Artikelnummer";"Bezeichnung";"Einheit";"Steuerart";"VK (Netto)"\n'
        b'"7000411";"Service \x96 Test";"Stk";"USt19";"420,00"\n'
    )
    csv_path.write_bytes(content)

    rows = ArticlesCsvImporter().load(str(csv_path))

    assert len(rows) == 1
    assert rows[0]["Artikelnummer"] == "7000411"
    assert "Service" in rows[0]["Bezeichnung"]
