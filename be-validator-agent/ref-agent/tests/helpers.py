import copy

from refagent import agent
from refagent.api import HttpClient

from conftest import KEY


def run(base_url, case_id, listed, backend=None, rules=None, **kw):
    cfg = rules if isinstance(rules, dict) else agent.load_rules(rules or agent.DEFAULT_RULES)
    http = HttpClient(base_url, KEY, sleep=lambda s: None)
    return agent.validate_case(case_id, http, listed, cfg, backend, **kw)


def listed_of(stub, case_id):
    return [{"document_id": d["id"], "filename": d["title"]} for d in stub.cases[case_id].values()]


def titles(rep, severity=None):
    return sorted((f["rule_id"], f["title"], f["severity"]) for f in rep["findings"] if severity in (None, f["severity"]) and f["source"] == "rule")


def tool_use(name, inp, use_id="tu-1"):
    return {"output": {"message": {"role": "assistant", "content": [{"toolUse": {"toolUseId": use_id, "name": name, "input": inp}}]}},
            "usage": {"inputTokens": 100, "outputTokens": 20}}


def submit(explanations=(), extra=(), summary="Shrnutí."):
    return tool_use("submit_assessment", {"explanations": list(explanations), "extra_concerns": list(extra), "summary": summary}, "tu-sub")


class FakeBackend:
    """Nahrazuje ConverseBackend: vrací připravené odpovědi a zaznamenává, co dostal."""
    model_id = "fake-model"

    def __init__(self, *scripted):
        self.scripted, self.calls, self.requests, self.usage = list(scripted), 0, [], {"inputTokens": 0, "outputTokens": 0}

    def converse(self, system, messages, tool_names, forced=None):
        self.calls += 1
        self.requests.append({"system": system, "messages": copy.deepcopy(messages), "tools": list(tool_names), "forced": forced})
        r = self.scripted.pop(0)
        return r(self.requests[-1]) if callable(r) else r
