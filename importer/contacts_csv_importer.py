import csv
from pathlib import Path


class ContactsCsvImporter:
    def load(self, file_path: str) -> list[dict]:
        path = Path(file_path)
        encodings = ["utf-8-sig", "cp1252", "latin-1"]

        last_error = None
        for encoding in encodings:
            try:
                with open(path, "r", encoding=encoding, newline="") as f:
                    sample = f.read(4096)
                    f.seek(0)

                    delimiter = ";"
                    try:
                        dialect = csv.Sniffer().sniff(sample, delimiters=";,")
                        delimiter = dialect.delimiter
                    except Exception:
                        pass

                    reader = csv.DictReader(f, delimiter=delimiter)
                    rows = list(reader)

                    cleaned_rows: list[dict] = []
                    for row in rows:
                        if not isinstance(row, dict):
                            continue
                        cleaned = {str(k or "").lstrip("?\ufeff").strip(): v for k, v in row.items()}
                        cleaned_rows.append(cleaned)

                    return cleaned_rows
            except UnicodeDecodeError as exc:
                last_error = exc
                continue

        if last_error is not None:
            raise last_error
        return []
