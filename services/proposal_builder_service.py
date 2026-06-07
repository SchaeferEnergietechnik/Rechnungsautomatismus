class ProposalBuilderService:
    def build_proposal_candidates(self, blocks: list[dict], classifier) -> list[dict]:
        proposals: list[dict] = []

        for block in blocks:
            block_type, reason = classifier.classify(block)

            if block_type not in {"einsatz", "prueffall"}:
                continue

            proposal = {
                "mitarbeiter": block.get("mitarbeiter", ""),
                "kw": block.get("kw", ""),
                "datum": block.get("datum", ""),
                "wochentag": block.get("wochentag", ""),
                "kunde_roh": block.get("kunde", "").strip(),
                "projekt_roh": block.get("projekt", "").strip(),
                "adresse_roh": block.get("adresse", "").strip(),
                "ansprechpartner_roh": block.get("ansprechpartner", "").strip(),
                "auftrag_roh": block.get("auftrag", "").strip(),
                "bemerkungen_roh": block.get("bemerkungen", "").strip(),
                "re_roh": block.get("re", "").strip(),
                "klassifikation": block_type,
                "klassifikationsgrund": reason,
            }

            proposals.append(proposal)

        return proposals
