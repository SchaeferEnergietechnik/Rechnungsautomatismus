import csv
from pathlib import Path


class ContactsCsvImporter:
    def load(self, file_path: str) -> list[dict]:
        with open(Path(file_path), "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f, delimiter=";")
            return list(reader)
