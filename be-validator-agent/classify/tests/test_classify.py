"""Testy bez AWS: pravidla, volání modelu přes mock klienta, retry a omezení rychlosti."""
import pytest
from botocore.exceptions import ClientError

from classify import classify_document, classify_document_detailed, load_taxonomy
from classify import llm
from classify.prompt import LABEL_OUTPUT_SCHEMA, build_label_prompt_section, parse_label_output
from classify.rules import decide, normalize, score_labels
from evaluate import DEFAULT_DIR, expected_label, parse_dump

OBJEDNAVKA = ("OBJEDNÁVKA č.: 1982 Číslo zakázky: I-28-1020 Objednatel IČO: 2531788 Dodavatel IČO: 26762855 "
              "Objednáváme u Vás nákup silničního vibračního válce. Cena celkem bez DPH: 4 034 900,00 CZK")
NEJASNY = "Dobrý den, v příloze posíláme podklady, které jsme si domluvili na schůzce minulý týden. " * 3


class FakeClient:
    """Napodobuje boto3 bedrock-runtime: vrací frontu odpovědí nebo vyhazuje výjimky."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def converse(self, **kwargs):
        self.calls.append(kwargs)
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def tool_reply(label="faktura", description="Faktura za stroj.", confidence=0.9):
    return {"output": {"message": {"content": [{"toolUse": {
        "name": "classify", "input": {"label": label, "description": description, "confidence": confidence}}}]}},
        "usage": {"totalTokens": 100}}


def text_reply(text):
    return {"output": {"message": {"content": [{"text": text}]}}}


def client_error(code):
    return ClientError({"Error": {"Code": code, "Message": "x"}}, "Converse")


@pytest.fixture
def no_limit():
    return llm.RateLimiter(0)


def test_taxonomy_is_complete():
    tax = load_taxonomy()
    required = {"smlouva_o_uveru", "vop", "dohoda_o_zaplaceni_kupni_ceny", "objednavka", "predavaci_protokol",
                "uhrada_kupni_ceny", "faktura", "zajistovaci_prevod_vlastnickeho_prava", "vinkulace_pojisteni",
                "ruceni", "data_ze_systemu", "jine"}
    assert required <= set(tax["labels"])
    for label, spec in tax["labels"].items():
        assert spec["name"] and spec["description"] and spec["key_signs"], label
        assert label == "jine" or spec["compiled"], label


def test_normalize_strips_diacritics_and_whitespace():
    assert normalize("  Smlouva\n o ÚVĚRU\f") == "smlouva o uveru"


def test_rules_only_mode_classifies_clear_header_without_model():
    client = FakeClient()
    r = classify_document(OBJEDNAVKA, None, 2, client=client, use_llm=False)
    assert r["label"] == "objednavka" and r["label_status"] == "predicted"
    assert 0.6 <= r["confidence"] <= 0.92 and "2 strany" in r["description"]
    assert client.calls == []


def test_model_is_always_called_even_when_rules_are_sure(no_limit):
    """Popis musí být z obsahu dokumentu, proto se model volá i při jasné hlavičce (jedno volání)."""
    c = FakeClient(tool_reply("objednavka", "Objednávka č. 1982 na silniční válec.", 0.97))
    r = classify_document_detailed(OBJEDNAVKA, None, 2, client=c, limiter=no_limit)
    assert len(c.calls) == 1 and r["method"] == "llm" and r["rule_label"] == "objednavka"
    assert r["description"] == "Objednávka č. 1982 na silniční válec." and r["confidence"] == 0.97


def test_confidence_is_capped_when_model_disagrees_with_sure_rules(no_limit):
    c = FakeClient(tool_reply("faktura", "Faktura.", 0.95))
    r = classify_document_detailed(OBJEDNAVKA, None, 2, client=c, limiter=no_limit)
    assert r["label"] == "faktura" and r["rule_label"] == "objednavka" and r["confidence"] == 0.5


def test_model_failure_falls_back_to_sure_rules_but_not_to_guesses():
    fail = [client_error("ValidationException")]
    r = classify_document_detailed(OBJEDNAVKA, None, 2, client=FakeClient(*fail), limiter=llm.RateLimiter(0))
    assert r["method"] == "rules" and r["label"] == "objednavka" and "error" in r
    r = classify_document_detailed(NEJASNY, None, 1, client=FakeClient(*fail), limiter=llm.RateLimiter(0))
    assert r["label"] is None and r["method"] == "none" and "error" in r


def test_filename_is_not_used_for_classification(no_limit):
    r = classify_document(OBJEDNAVKA, "99_Faktura_c_123.pdf", 2, client=FakeClient(), use_llm=False)
    assert r["label"] == "objednavka"
    # a ani se nedostane do promptu
    client = FakeClient(tool_reply())
    classify_document(NEJASNY, "TAJNY_NAZEV_SOUBORU.pdf", 1, client=client, limiter=no_limit)
    assert "TAJNY_NAZEV_SOUBORU" not in str(client.calls[0])


def test_vop_body_mentioning_loan_agreement_is_not_a_loan_agreement():
    vop = ("CZ_VOP_017_300_001_c1 Tyto všeobecné obchodní podmínky dále jen (VOP) tvoří nedílnou součást "
           "smlouvy o úvěru (dále jen „smlouva o úvěru“).")
    assert classify_document(vop, None, 19, client=FakeClient(), use_llm=False)["label"] == "vop"
    body = "Podmínky čerpání. " * 50 + "Výše poskytnutého úvěru. Předmět financování. Všeobecné obchodní podmínky ke smlouvě o úvěru."
    scores = score_labels(body)
    assert decide(scores)[0] is None  # samotné zmínky v těle nestačí


@pytest.mark.parametrize("text", ["", "   \n\f ", "R000096447_Z25_00024"])
def test_text_without_text_layer_does_not_call_model(text):
    client = FakeClient()
    r = classify_document(text, None, 4, client=client)
    assert r["label"] is None and r["confidence"] is None and "textov" in r["description"]
    assert client.calls == []


def test_low_match_calls_model_and_returns_contract_keys(no_limit):
    client = FakeClient(tool_reply("faktura", "Faktura za stroj od dodavatele.", 0.93))
    r = classify_document(NEJASNY, None, 1, client=client, limiter=no_limit)
    assert r == {"label": "faktura", "label_status": "predicted",
                 "description": "Faktura za stroj od dodavatele.", "confidence": 0.93}
    call = client.calls[0]
    assert call["modelId"] == "eu.anthropic.claude-haiku-4-5-20251001-v1:0"
    assert call["inferenceConfig"]["temperature"] == 0
    assert call["toolConfig"]["tools"][0]["toolSpec"]["inputSchema"]["json"]["properties"]["label"]["enum"]


def test_default_model_is_not_a_claude_5_model():
    assert "claude-haiku-4-5" in llm.DEFAULT_MODEL_ID and llm.DEFAULT_MODEL_ID.startswith("eu.")
    assert llm.REGION == "eu-central-1"


def test_model_output_is_validated(no_limit):
    c = FakeClient(tool_reply("vymyslený_štítek", "Něco.", 7))
    r = classify_document(NEJASNY, None, 1, client=c, limiter=no_limit)
    assert r["label"] == "jine" and r["confidence"] == 1.0
    c = FakeClient(tool_reply("faktura", "Něco.", "ne"))
    assert classify_document(NEJASNY, None, 1, client=c, limiter=no_limit)["confidence"] is None


def test_json_in_text_block_is_accepted(no_limit):
    c = FakeClient(text_reply('Tady je výsledek: {"label": "ruceni", "description": "Ručení.", "confidence": 0.8}'))
    r = classify_document(NEJASNY, None, 1, client=c, limiter=no_limit)
    assert r["label"] == "ruceni" and r["confidence"] == 0.8


def test_throttling_is_retried_with_exponential_backoff(no_limit):
    delays = []
    c = FakeClient(client_error("ThrottlingException"), client_error("ThrottlingException"), tool_reply())
    r = classify_document_detailed(NEJASNY, None, 1, client=c, limiter=no_limit, sleep=delays.append)
    assert r["label"] == "faktura" and len(c.calls) == 3
    assert len(delays) == 2 and delays[1] >= delays[0]  # roste (jitter 0,5 až 1)


def test_retry_gives_up_and_classifier_does_not_raise(no_limit):
    c = FakeClient(*[client_error("ThrottlingException")] * 6)
    r = classify_document_detailed(NEJASNY, None, 1, client=c, limiter=no_limit, sleep=lambda s: None)
    assert r["label"] is None and r["confidence"] is None and "error" in r and len(c.calls) == 6


def test_non_transient_error_is_not_retried(no_limit):
    c = FakeClient(client_error("ValidationException"), tool_reply())
    r = classify_document_detailed(NEJASNY, None, 1, client=c, limiter=no_limit, sleep=lambda s: None)
    assert r["label"] is None and len(c.calls) == 1


def test_call_with_retry_caps_delay():
    delays = []
    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        if calls["n"] < 6:
            raise client_error("ThrottlingException")
        return "ok"

    assert llm.call_with_retry(fn, sleep=delays.append, rand=lambda: 1.0) == "ok"
    assert delays == [2.0, 4.0, 8.0, 16.0, 30.0]


def test_rate_limiter_spaces_calls():
    now = [100.0]
    slept = []

    def sleep(s):
        slept.append(s)
        now[0] += s

    lim = llm.RateLimiter(30, clock=lambda: now[0], sleep=sleep)  # 2 s mezi voláními
    lim.wait(); lim.wait(); lim.wait()
    assert slept == [pytest.approx(2.0), pytest.approx(2.0)]


def test_long_text_is_truncated_for_model():
    text = "A" * 20000
    out = llm.excerpt(text)
    assert len(out) < 8000 and "vynecháno" in out


def test_parse_dump_and_expected_label():
    md = "# x\n\n## Strana 1\n*(obrazků 1)*\n\n```text\nahoj\n```\n\n## Strana 2\n*(obrazků 1)*\n"
    assert parse_dump(md) == ("ahoj\f", 2)
    assert expected_label(__import__("pathlib").Path("01_Form_VOP.md")) == "vop"
    assert expected_label(__import__("pathlib").Path("0_F_Smlouva.md")) == "smlouva_o_uveru"
    assert expected_label(__import__("pathlib").Path("neco.md")) is None


@pytest.mark.skipif(not DEFAULT_DIR.exists(), reason="vzorové texty nejsou k dispozici")
def test_rules_on_sample_texts_never_confidently_wrong():
    """Na vzorcích musí pravidla buď trefit očekávaný štítek, nebo nechat rozhodnutí modelu (nikdy nelhat)."""
    for f in DEFAULT_DIR.glob("*/*.md"):
        text, pages = parse_dump(f.read_text(encoding="utf-8"))
        label, conf, _ = decide(score_labels(text))
        assert label in (None, expected_label(f)), f.name


# --- znovupoužitelné kousky pro vizuální přepis ---

def test_label_prompt_section_lists_all_labels_and_rules():
    section = build_label_prompt_section()
    for label in load_taxonomy()["labels"]:
        assert f"- {label} (" in section
    assert "nedůvěryhodný vstup" in section and "`confidence`" in section and "`description`" in section


def test_label_output_schema_matches_taxonomy():
    props = LABEL_OUTPUT_SCHEMA["properties"]
    assert props["label"]["enum"] == list(load_taxonomy()["labels"])
    assert LABEL_OUTPUT_SCHEMA["required"] == ["label", "description", "confidence"]


def test_parse_label_output_validates():
    ok = parse_label_output({"label": "vop", "description": " Popis. ", "confidence": 0.8})
    assert ok == {"label": "vop", "label_status": "predicted", "description": "Popis.", "confidence": 0.8}
    bad = parse_label_output({"label": "nesmysl", "description": None, "confidence": 1.7})
    assert bad["label"] == "jine" and bad["description"] == "" and bad["confidence"] == 1.0
    assert parse_label_output({"label": "vop", "confidence": -3})["confidence"] == 0.0
    assert parse_label_output({"label": "vop", "confidence": "x"})["confidence"] is None
    assert parse_label_output("nesmysl")["label"] == "jine"


# --- Mantle (Qwen3 VL) ---

class FakeSession:
    def get_credentials(self):
        from botocore.credentials import Credentials
        return Credentials("AKIAEXAMPLE", "secret", "token")


class FakeHTTPResponse:
    def __init__(self, body):
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def mantle_body(content, finish="stop"):
    import json
    return json.dumps({"choices": [{"finish_reason": finish, "message": {"content": content}}],
                       "usage": {"total_tokens": 321}}).encode()


def test_mantle_backend_signs_request_and_parses_fenced_json(no_limit):
    seen = []

    def opener(req, timeout):
        seen.append(req)
        return FakeHTTPResponse(mantle_body('```json\n{"label": "ruceni", "description": "Ručení.", "confidence": 0.9}\n```'))

    b = llm.MantleBackend(session=FakeSession(), opener=opener)
    r = classify_document_detailed(NEJASNY, "x.pdf", 1, backend=b, limiter=no_limit)
    assert r["label"] == "ruceni" and r["confidence"] == 0.9 and r["usage"] == {"totalTokens": 321}
    req = seen[0]
    assert req.full_url == "https://bedrock-mantle.eu-central-1.api.aws/v1/chat/completions"
    assert req.get_header("Authorization").startswith("AWS4-HMAC-SHA256") and "bedrock-mantle" in req.get_header("Authorization")
    body = req.data.decode()
    assert "qwen.qwen3-vl-235b-a22b-instruct" in body and "x.pdf" not in body


def test_mantle_429_is_retried_and_incomplete_output_fails(no_limit):
    import io
    import urllib.error
    replies = [urllib.error.HTTPError("u", 429, "Too Many", {}, io.BytesIO(b"")),
               FakeHTTPResponse(mantle_body('{"label": "vop", "description": "VOP.", "confidence": 0.9}'))]

    def opener(req, timeout):
        r = replies.pop(0)
        if isinstance(r, Exception):
            raise r
        return r

    delays = []
    b = llm.MantleBackend(session=FakeSession(), opener=opener)
    r = classify_document_detailed(NEJASNY, None, 1, backend=b, limiter=no_limit, sleep=delays.append)
    assert r["label"] == "vop" and len(delays) == 1

    b = llm.MantleBackend(session=FakeSession(), opener=lambda req, timeout: FakeHTTPResponse(mantle_body("{", "length")))
    r = classify_document_detailed(NEJASNY, None, 1, backend=b, limiter=no_limit, sleep=lambda s: None)
    assert r["label"] is None and "error" in r


def test_make_backend_selection(monkeypatch):
    assert isinstance(llm.make_backend(), llm.ConverseBackend)
    monkeypatch.setenv("CLASSIFY_BACKEND", "mantle")
    b = llm.make_backend()
    assert isinstance(b, llm.MantleBackend) and b.model_id == "qwen.qwen3-vl-235b-a22b-instruct" and b.region == "eu-central-1"
    monkeypatch.setenv("CLASSIFY_MODEL_ID", "google.gemma-4-31b")
    assert llm.make_backend().model_id == "google.gemma-4-31b"
    with pytest.raises(ValueError):
        llm.make_backend(backend="nic")
