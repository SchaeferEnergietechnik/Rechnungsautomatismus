from pathlib import Path


class EnvLoader:
    @staticmethod
    def load_from_file(file_path: str = ".env") -> None:
        path = Path(file_path)
        if not path.exists() or not path.is_file():
            return

        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key:
                # Existing environment variables win over .env entries.
                import os

                os.environ.setdefault(key, value)
