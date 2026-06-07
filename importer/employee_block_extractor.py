class EmployeeBlockExtractor:
    def extract_blocks_from_row(self, row_values: list[str], block_configs: list[dict]) -> list[dict]:
        blocks: list[dict] = []

        for block in block_configs:
            start = block["start_column"]
            field_order = block["field_order"]

            block_data: dict = {
                "block_index": block["index"],
                "mitarbeiter": block["employee_name"]
            }

            for offset, field_name in enumerate(field_order):
                column_index = start + offset
                value = row_values[column_index] if column_index < len(row_values) else ""
                block_data[field_name] = value.strip() if isinstance(value, str) else value

            blocks.append(block_data)

        return blocks

    def is_block_meaningfully_filled(self, block: dict) -> bool:
        relevant_fields = [
            "status_oder_kunde",
            "kunde",
            "projekt",
            "adresse",
            "ansprechpartner",
            "auftrag",
            "bemerkungen",
            "re",
        ]

        for field in relevant_fields:
            value = str(block.get(field, "")).strip()
            if value and value not in {"-", "--"}:
                return True

        return False
