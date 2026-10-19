"""LLM vrstva s mockovaným modelem: počet volání, tool loop, hranice toho, co model smí změnit, a Converse backend s falešným klientem."""
import json

import pytest

from conftest import KEY, clean_case
from helpers import FakeBackend, listed_of, run, submit, tool_use
from refagent import agent, llm


def case_with_issue(stub):
    cid = clean_case(stub)
    stub.cases[cid]["d-order"]["text"] = "Objednávka k smlouvě č. 7777/25\nVýr. č.: SN1234567\nCena celkem bez DPH:\n1 000 000,00 CZK\n"
    return cid


def go(stub, cid, backend, **kw):
    kw.setdefault("llm_tools", False)
    return run(stub.base_url, cid, listed_of(stub, cid), backend=backend, **kw)


def finding_id(stub, cid):
    rep = go(stub, cid, None)
    return next(f["id"] for f in rep["findings"] if f["rule_id"] == "R-CONTRACT-NO" and f["severity"] == "review")


def test_one_llm_call_explains_findings(stub):
    cid = case_with_issue(stub)
    fid = finding_id(stub, cid)
    b = FakeBackend(submit([{"finding_id": fid, "text": "Objednávka odkazuje na jinou smlouvu.", "assessment": "likely_real"}], summary="Případ má nesoulad čísla smlouvy."))
    rep = go(stub, cid, b)
    assert b.calls == 1 and rep["llm"]["calls"] == 1 and rep["llm"]["used"]
    f = next(f for f in rep["findings"] if f["id"] == fid)
    assert "jinou smlouvu" in f["explanation"] and "spíš skutečný problém" in f["explanation"]
    assert rep["llm"]["summary"].startswith("Případ")
    assert rep["recommendation"] == agent.REC_REVIEW


def test_no_findings_means_zero_llm_calls(stub):
    cid = clean_case(stub)
    b = FakeBackend()
    rep = go(stub, cid, b)
    assert b.calls == 0 and rep["recommendation"] == agent.REC_APPROVE and not rep["llm"]["used"]


def test_tool_loop_uses_data_tool_then_submits(stub):
    cid = case_with_issue(stub)
    fid = finding_id(stub, cid)
    b = FakeBackend(tool_use("get_document_signatures", {"document_id": "d-order", "match_client": True, "include_vectors": True}),
                    submit([{"finding_id": fid, "text": "Vysvětlení."}]))
    rep = go(stub, cid, b, llm_tools=True)
    assert b.calls == 2 and rep["llm"]["calls"] == 2
    result_msg = b.requests[1]["messages"][-1]
    tr = result_msg["content"][0]["toolResult"]
    assert tr["status"] == "success" and tr["content"][0]["json"]["signatures"]
    # i když model žádá vektory, kód posílá include_vectors=false
    q = [q for p, q in stub.requests if p.endswith("/d-order/signatures")][-1]
    assert q["include_vectors"] == ["false"]


def test_model_cannot_read_other_case_or_unknown_document(stub):
    cid = case_with_issue(stub)
    other = clean_case(stub, "CASE-OTHER")
    stub.cases[other]["d-secret"] = dict(id="d-secret", title="tajny.pdf", text="TAJNÝ OBSAH", label="faktura")
    fid = finding_id(stub, cid)
    b = FakeBackend(tool_use("get_document", {"case_id": other, "document_id": "d-secret"}), submit([{"finding_id": fid, "text": "x"}]))
    go(stub, cid, b, llm_tools=True)
    tr = b.requests[1]["messages"][-1]["content"][0]["toolResult"]
    assert tr["status"] == "error" and "TAJNÝ" not in str(tr)
    assert not any("d-secret" in p for p, _ in stub.requests)


def test_get_document_tool_truncates_text_and_marks_untrusted(stub):
    cid = case_with_issue(stub)
    stub.cases[cid]["d-order"]["text"] += "x" * 20000
    fid = finding_id(stub, cid)
    b = FakeBackend(tool_use("get_document", {"document_id": "d-order"}), submit([{"finding_id": fid, "text": "x"}]))
    go(stub, cid, b, llm_tools=True)
    out = b.requests[1]["messages"][-1]["content"][0]["toolResult"]["content"][0]["json"]
    assert len(out["text"]) <= llm.MAX_TOOL_TEXT and out["text_truncated"] and "nedůvěryhodný" in out["_note"]


def test_call_budget_forces_submit_on_last_call(stub):
    cid = case_with_issue(stub)
    b = FakeBackend(tool_use("list_case_documents", {}), tool_use("list_case_documents", {}, "tu-2"), submit(summary="hotovo"))
    rep = go(stub, cid, b, max_llm_calls=3, llm_tools=True)
    assert b.calls == 3 and b.requests[-1]["tools"] == ["submit_assessment"] and b.requests[-1]["forced"] == "submit_assessment"
    assert rep["llm"]["summary"] == "hotovo"


def test_llm_failure_keeps_rule_findings(stub):
    cid = case_with_issue(stub)

    class Boom(FakeBackend):
        def converse(self, *a, **k):
            self.calls += 1
            raise llm.LlmError("Volání modelu selhalo: ThrottlingException")
    rep = go(stub, cid, Boom())
    assert rep["llm"]["error"] and rep["recommendation"] == agent.REC_REVIEW
    assert any(f["rule_id"] == "R-CONTRACT-NO" for f in rep["findings"])


def test_llm_can_only_add_findings_with_real_quotes(stub):
    cid = case_with_issue(stub)
    good = {"title": "Zvláštní věta", "text": "V objednávce je podezřelá věta.", "document": "D2", "quote": "Výr. č.: SN1234567"}
    fake = {"title": "Vymyšlené", "text": "Nic takového tam není.", "document": "D2", "quote": "tato věta v dokumentu není"}
    b = FakeBackend(submit(extra=[good, fake]))
    before = go(stub, cid, None)
    rep = go(stub, cid, b)
    llm_f = [f for f in rep["findings"] if f["source"] == "llm"]
    assert len(llm_f) == 1 and llm_f[0]["severity"] == "review" and llm_f[0]["evidence"][0]["quote"] == good["quote"]
    assert llm_f[0]["evidence"][0]["document_id"] == "d-order" and llm_f[0]["evidence"][0]["page"] == 1
    assert len(rep["findings"]) == len(before["findings"]) + 1


# ------------------------------------------------------------------ Converse backend (falešný klient)

class FakeClient:
    def __init__(self, *outcomes):
        self.outcomes, self.kwargs = list(outcomes), []

    def converse(self, **kw):
        self.kwargs.append(kw)
        o = self.outcomes.pop(0)
        if isinstance(o, Exception):
            raise o
        return o


class AwsError(Exception):
    def __init__(self, code, msg=""):
        super().__init__(msg or code)
        self.response = {"Error": {"Code": code}}


def test_converse_request_shape_and_usage():
    c = FakeClient(submit())
    b = llm.ConverseBackend(client=c, max_rpm=0)
    b.converse("sys", [{"role": "user", "content": [{"text": "x"}]}], ["get_document", "submit_assessment"])
    kw = c.kwargs[0]
    assert kw["modelId"] == llm.DEFAULT_MODEL_ID and kw["system"] == [{"text": "sys"}]
    assert [t["toolSpec"]["name"] for t in kw["toolConfig"]["tools"]] == ["get_document", "submit_assessment"]
    assert kw["toolConfig"]["toolChoice"] == {"any": {}} and kw["inferenceConfig"]["temperature"] == 0
    assert all("inputSchema" in t["toolSpec"] and "json" in t["toolSpec"]["inputSchema"] for t in kw["toolConfig"]["tools"])
    assert b.usage == {"inputTokens": 100, "outputTokens": 20}
    # forced
    c.outcomes.append(submit())
    b.converse("sys", [], ["submit_assessment"], forced="submit_assessment")
    assert c.kwargs[1]["toolConfig"]["toolChoice"] == {"tool": {"name": "submit_assessment"}}


def test_converse_retries_throttling_and_gives_up_on_other_errors():
    slept = []
    c = FakeClient(AwsError("ThrottlingException"), AwsError("ThrottlingException"), submit())
    b = llm.ConverseBackend(client=c, max_rpm=0, sleep=slept.append)
    assert b.converse("s", [], ["submit_assessment"])
    assert b.calls == 3 and slept == [2, 4]
    c2 = FakeClient(AwsError("AccessDeniedException"))
    with pytest.raises(llm.LlmError) as e:
        llm.ConverseBackend(client=c2, max_rpm=0, sleep=slept.append).converse("s", [], ["submit_assessment"])
    assert "AccessDeniedException" in str(e.value) and len(c2.kwargs) == 1


def test_converse_falls_back_to_auto_tool_choice():
    c = FakeClient(AwsError("ValidationException", "This model doesn't support toolChoice any"), submit())
    b = llm.ConverseBackend(client=c, max_rpm=0, sleep=lambda s: None)
    b.converse("s", [], ["submit_assessment"])
    assert c.kwargs[1]["toolConfig"]["toolChoice"] == {"auto": {}}


@pytest.mark.parametrize("model", ["eu.anthropic.claude-opus-5-5", "global.anthropic.claude-fable-5-1", "eu.anthropic.claude-haiku-5-5", "eu.anthropic.claude-sonnet-5-5"])
def test_models_55_are_refused(model):
    with pytest.raises(ValueError):
        llm.ConverseBackend(model_id=model, client=FakeClient())


@pytest.mark.parametrize("model", ["eu.anthropic.claude-haiku-4-5-20251001-v1:0", "eu.anthropic.claude-sonnet-4-5-20250929-v1:0", "qwen.qwen3-235b-a22b-2507-v1:0"])
def test_allowed_models_pass(model):
    assert llm.ConverseBackend(model_id=model, client=FakeClient()).model_id == model


def test_region_is_fixed_to_frankfurt():
    with pytest.raises(ValueError):
        llm.ConverseBackend(region="eu-north-1", client=FakeClient())


def test_default_is_one_call_and_only_submit_tool_offered(stub):
    cid = case_with_issue(stub)
    b = FakeBackend(submit(summary="ok"))
    go(stub, cid, b)
    assert b.calls == 1 and b.requests[0]["tools"] == ["submit_assessment"] and b.requests[0]["forced"] == "submit_assessment"


def test_only_review_findings_are_sent_to_model(stub):
    cid = case_with_issue(stub)
    b = FakeBackend(submit(summary="ok"))
    rep = go(stub, cid, b)
    sent = json.loads(b.requests[0]["messages"][0]["content"][0]["text"].split("\n", 1)[1])["findings"]
    assert sent and {f["severity"] for f in sent} == {"review"}
    assert len(sent) < len(rep["findings"])


@pytest.mark.parametrize("text,dropped", [
    ("Podpis chybí na straně 4.", True),
    ("Dokument je nepodepsaný.", True),
    ("Podpis je padělaný.", True),
    ("Detektor nenašel podpis; neznamená to, že podpis chybí.", False),
    ("Zkontrolujte výřez podpisu na straně 4.", False),
])
def test_explanations_that_overclaim_about_signatures_are_dropped(stub, text, dropped):
    cid = case_with_issue(stub)
    fid = finding_id(stub, cid)
    rep = go(stub, cid, FakeBackend(submit([{"finding_id": fid, "text": text}])))
    expl = next(f for f in rep["findings"] if f["id"] == fid)["explanation"]
    assert ("vynecháno" in expl) is dropped


def test_arrays_returned_as_json_strings_are_accepted(stub):
    cid = case_with_issue(stub)
    fid = finding_id(stub, cid)
    resp = tool_use("submit_assessment", {"explanations": json.dumps([{"finding_id": fid, "text": "Z řetězce."}]), "extra_concerns": "nesmysl", "summary": "s"})
    rep = go(stub, cid, FakeBackend(resp))
    assert next(f for f in rep["findings"] if f["id"] == fid)["explanation"].startswith("Z řetězce")


def test_broken_json_string_with_inner_quotes_is_salvaged(stub):
    cid = case_with_issue(stub)
    fid = finding_id(stub, cid)
    broken = ('[\n  {\n    "finding_id": "%s",\n    "assessment": "unclear",\n    "text": "Smlouva vyžaduje "kopii dokladu" a ta chybí v sadě."\n  },\n'
              '  {\n    "finding_id": "F-9999",\n    "text": "Jiné."\n  }\n]') % fid
    resp = tool_use("submit_assessment", {"explanations": broken, "summary": "s"})
    rep = go(stub, cid, FakeBackend(resp))
    f = next(f for f in rep["findings"] if f["id"] == fid)
    assert '"kopii dokladu"' in f["explanation"] and "nejasné" in f["explanation"]


def test_aliases_are_translated_back_for_the_reader(stub):
    cid = case_with_issue(stub)
    fid = finding_id(stub, cid)
    resp = submit([{"finding_id": fid, "text": "D2 uvádí „7777/25“ (Q2), ale D1 má jiné číslo."}], summary="Problém v D2.")
    rep = go(stub, cid, FakeBackend(resp))
    f = next(f for f in rep["findings"] if f["id"] == fid)
    assert "objednavka.pdf" in f["explanation"] and "smlouva.pdf" in f["explanation"] and "D2" not in f["explanation"] and "Q2" not in f["explanation"]
    assert rep["llm"]["summary"] == "Problém v objednavka.pdf."
