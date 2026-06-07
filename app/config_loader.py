import json
from pathlib import Path


class ConfigLoader:
    def __init__(self, config_root: str = "config") -> None:
        self.config_root = Path(config_root)

    def load_json(self, filename: str) -> dict:
        with open(self.config_root / filename, "r", encoding="utf-8-sig") as f:
            return json.load(f)
