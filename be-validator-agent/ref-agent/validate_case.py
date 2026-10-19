#!/usr/bin/env python3
"""Referenční validační agent: projde případ přes agent API a vypíše report s nálezy a doporučením.

    AGENT_API_KEY=... python3 validate_case.py --case-id X --base-url http://localhost:8099/v1 --no-llm
    AGENT_API_KEY=... INGEST_API_KEY=... python3 validate_case.py --case-id X --base-url URL/v1 --ingest-url URL2

Klíče jen z prostředí (AGENT_API_KEY, INGEST_API_KEY; AWS přihlášení pro Bedrock z profilu / prostředí). Nikdy se nevypisují.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from refagent import agent, llm, report                      # noqa: E402
from refagent.api import ApiError, HttpClient, documents_from_file, documents_from_ingest   # noqa: E402


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--case-id", required=True)
    p.add_argument("--base-url", required=True, help="agent API včetně /v1, např. http://localhost:8099/v1")
    src = p.add_mutually_exclusive_group()
    src.add_argument("--ingest-url", help="ingest API (jiná služba); seznam dokumentů z GET /cases/{case_id}/documents")
    src.add_argument("--documents-file", help="offline seznam dokumentů (JSON ve tvaru odpovědi ingest API)")
    p.add_argument("--rules", default=agent.DEFAULT_RULES, help="soubor s pravidly (výchozí rules.yaml)")
    p.add_argument("--no-llm", action="store_true", help="jen deterministická pravidla, žádné volání Bedrocku")
    p.add_argument("--model-id", default=os.environ.get("REF_AGENT_MODEL_ID", llm.DEFAULT_MODEL_ID),
                   help=f"Bedrock model / inference profil (výchozí {llm.DEFAULT_MODEL_ID}; modely 5.5 se nepoužívají)")
    p.add_argument("--llm-tools", action="store_true",
                   help="dá modelu i tři datové nástroje (dokument, vektory, podpisy); může stát víc volání modelu, výchozí je jedno")
    p.add_argument("--max-llm-calls", type=int, default=3, help="strop volání modelu na případ s --llm-tools (bez nich je to vždy 1)")
    p.add_argument("--json-out", help="uloží report i jako JSON")
    p.add_argument("--full-crop-urls", action="store_true",
                   help="ve výstupu nechá úplné předpodepsané adresy výřezů podpisů (platí 300 s, nesou dočasné přihlašovací údaje)")
    return p.parse_args(argv)


def main(argv=None):
    a = parse_args(argv)
    agent_key = os.environ.get("AGENT_API_KEY") or os.environ.get("API_KEY")
    ingest_key = os.environ.get("INGEST_API_KEY") or agent_key
    secrets = [agent_key, ingest_key]
    http = HttpClient(a.base_url, agent_key)
    try:
        if a.documents_file:
            listed, source = documents_from_file(a.documents_file), f"soubor {os.path.basename(a.documents_file)}"
        elif a.ingest_url:
            listed, source = documents_from_ingest(a.ingest_url, ingest_key, a.case_id), "ingest API"
        else:
            from refagent.api import AgentApi, list_all_documents
            api0 = AgentApi(http, a.case_id)
            listed, source = list_all_documents(lambda t: api0.list_case_documents(next_token=t)), "agent API (volání 0; ingest nezadán)"
            http.calls = 0
        cfg = agent.load_rules(a.rules)
        backend = None if a.no_llm else llm.ConverseBackend(model_id=a.model_id)
        rep = agent.validate_case(a.case_id, http, listed, cfg, backend, a.max_llm_calls, llm_tools=a.llm_tools)
    except (ApiError, ValueError, OSError) as e:
        print(report.redact(f"Chyba: {e}", secrets), file=sys.stderr)
        return 2
    rep["documents_source"] = source
    rep = report.redact(rep, secrets)
    if not a.full_crop_urls:
        rep = report.strip_signed_query(rep)
    print(report.render_text(rep))
    print(f"\nZdroj seznamu dokumentů: {source}")
    if a.json_out:
        with open(a.json_out, "w", encoding="utf-8") as f:
            f.write(report.render_json(rep))
    return 0


if __name__ == "__main__":
    sys.exit(main())
