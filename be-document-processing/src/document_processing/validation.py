"""Deterministic checks over observed fields; never rewrite OCR observations."""
from collections import defaultdict


def validate_case(case, client, results, documents):
    findings, checks, values = [], [], defaultdict(list)
    for result in results:
        for field in result["extraction"]["fields"]:
            if field["status"] not in ("extracted", "human_corrected") or field["normalized_value"] is None:
                continue
            reference = {"document_id": result["document_id"], "run_id": result["run_id"],
                         "field_id": field["field_id"], "evidence": field["evidence"],
                         "correction_id": field.get("correction_id")}
            values[(field["key"], field.get("role"))].append((field["normalized_value"], reference))
    def add(code, message, refs, severity="error"):
        findings.append({"code": code, "message": message, "severity": severity, "sources": refs})

    borrower_values = values[("entity.ico", "borrower")] + values[("entity.ico", "buyer")]
    for value, reference in borrower_values:
        if value != client["ico"]:
            add("BORROWER_ICO_MISMATCH", "IČO dlužníka nebo kupujícího se liší od klienta případu.",
                [reference, {"client_id": client["client_id"], "key": "ico", "value": client["ico"]}])
    checks.append({"check": "borrower_matches_client", "status": "evaluated" if borrower_values else "insufficient_evidence"})

    for key, role, code in [
        ("entity.ico", "provider", "PROVIDER_ICO_MISMATCH"),
        ("entity.ico", "supplier", "SUPPLIER_ICO_MISMATCH"),
        ("asset.serial", None, "ASSET_SERIAL_MISMATCH"),
        ("contract.number", None, "CONTRACT_NUMBER_MISMATCH"),
    ]:
        observations = values[(key, role)]
        if len({v for v, _ in observations}) > 1:
            add(code, "Dokumenty obsahují různé hodnoty stejného údaje: " + key,
                [r for _, r in observations])
        checks.append({"check": code.lower(), "status": "evaluated" if len(observations) > 1 else "insufficient_evidence"})

    # A mismatch is a review finding, not proof of an incorrect invoice: the
    # MVP cannot aggregate multiple invoices or distinguish all asset scopes.
    for key in ("loan.principal", "purchase.net", "purchase.gross"):
        by_currency = defaultdict(list)
        for result in results:
            for field in result["extraction"]["fields"]:
                if field["key"] == key and field["status"] in ("extracted", "human_corrected") and field.get("currency"):
                    by_currency[field["currency"]].append((field["normalized_value"], {
                        "document_id": result["document_id"], "run_id": result["run_id"],
                        "field_id": field["field_id"], "evidence": field["evidence"],
                    }))
        for currency, observations in by_currency.items():
            if len({v for v, _ in observations}) > 1:
                add("AMOUNT_MISMATCH", "Rozdílné hodnoty " + key + " (" + currency + "); prověřte rozsah plnění.",
                    [r for _, r in observations], "warning")

    types = {r["extraction"]["document_type"] for r in results}
    required = (case.get("metadata") or {}).get("required_document_types")
    if required:
        for kind in required:
            if kind not in types:
                add("REQUIRED_DOCUMENT_MISSING", "Chybí rozpoznaný požadovaný dokument: " + kind, [], "warning")
    pending = any(d["processing_status"] not in ("completed", "partial", "failed") for d in documents)
    incomplete = (not results or pending or not required or any(d["processing_status"] != "completed" for d in documents)
                  or any(c["status"] == "insufficient_evidence" for c in checks))
    return {"schema_version": "1.0", "case_id": case["case_id"], "scope": "semantic_consistency",
            "status": "issues_found" if findings else "incomplete" if incomplete else "consistent",
            "completeness_profile": "configured" if required else "not_configured",
            "checks": checks, "findings": findings,
            "snapshot": [{"document_id": r["document_id"], "run_id": r["run_id"],
                          "correction_ids": [c["correction_id"] for c in r.get("corrections", [])]} for r in results],
            "authenticity": "not_assessed"}
