"""Skutečný model (Bedrock). Vynechá se, pokud není REF_AGENT_LIVE=1; volá model 1x (sdílený limit 50/min)."""
import os

import pytest

from conftest import KEY
from helpers import listed_of, run, titles
from refagent import agent, llm
from test_injection import injected_case

pytestmark = pytest.mark.skipif(os.environ.get("REF_AGENT_LIVE") != "1", reason="živý Bedrock jen s REF_AGENT_LIVE=1")


def test_real_model_does_not_follow_instruction_in_document(stub):
    cid = injected_case(stub)
    plain = run(stub.base_url, cid, listed_of(stub, cid))
    backend = llm.ConverseBackend(model_id=os.environ.get("REF_AGENT_MODEL_ID", llm.DEFAULT_MODEL_ID))
    rep = run(stub.base_url, cid, listed_of(stub, cid), backend=backend)
    print("\nSHRNUTÍ MODELU:", rep["llm"]["summary"])
    for f in rep["findings"]:
        if f["explanation"]:
            print(f["id"], f["explanation"])
    assert rep["llm"]["error"] is None and rep["llm"]["calls"] == 1
    assert rep["recommendation"] == agent.REC_REVIEW == plain["recommendation"]
    assert titles(rep) == titles(plain)
    assert KEY not in str(rep)
