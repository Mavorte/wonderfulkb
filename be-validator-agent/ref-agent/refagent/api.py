"""Klient agent API (čtyři čtecí volání) a seznam dokumentů z ingest API / souboru. Jen stdlib.

Klíč se bere z prostředí (předává ho volající), nikdy se nevypisuje: chybové zprávy ho neobsahují.
"""
import json
import time
import urllib.error
import urllib.parse
import urllib.request


class ApiError(Exception):
    """Chyba volání API. `status` je HTTP kód (0 = síť / nečitelná odpověď), `body` je dekódované tělo chyby."""

    def __init__(self, status, message, body=None):
        super().__init__(message)
        self.status = status
        self.body = body or {}


class HttpClient:
    def __init__(self, base_url, api_key=None, timeout=20, retries=3, sleep=time.sleep):
        self.base_url = base_url.rstrip("/")
        self._api_key = api_key
        self.timeout, self.retries, self._sleep = timeout, retries, sleep
        self.calls = 0

    def get(self, path, params=None):
        query = {k: _fmt(v) for k, v in (params or {}).items() if v is not None}
        url = self.base_url + path + ("?" + urllib.parse.urlencode(query) if query else "")
        headers = {"Accept": "application/json"}
        if self._api_key:
            headers["x-api-key"] = self._api_key
        last = None
        for attempt in range(self.retries + 1):
            self.calls += 1
            try:
                req = urllib.request.Request(url, headers=headers, method="GET")
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    return _decode(resp.read(), resp.status)
            except urllib.error.HTTPError as e:
                body = _safe_json(e.read())
                last = ApiError(e.code, f"HTTP {e.code} {path}: {body.get('error', '')}".strip(), body)
                if e.code < 500:   # 4xx se opakováním nezmění (409 řeší volající)
                    raise last
            except UnicodeEncodeError:
                raise ApiError(0, "API klíč obsahuje nepovolené znaky") from None
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                last = ApiError(0, f"Síťová chyba {path}: {type(e).__name__}")
            if attempt < self.retries:
                self._sleep(min(0.5 * 2 ** attempt, 4))
        raise last


def _fmt(v):
    return str(v).lower() if isinstance(v, bool) else str(v)


def _safe_json(raw):
    try:
        out = json.loads(raw.decode("utf-8"))
        return out if isinstance(out, dict) else {}
    except (ValueError, UnicodeDecodeError):
        return {}


def _decode(raw, status):
    try:
        return json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        raise ApiError(status, "Odpověď není platný JSON")


class AgentApi:
    """Tři nástroje agenta (volání 1 až 3) + seznam dokumentů (volání 0) nad agent API.

    Parametry, které řídí velikost odpovědi, se posílají vždy explicitně (include_values=false,
    include_vectors=false); model je změnit nemůže.
    """

    def __init__(self, http, case_id):
        self.http, self.case_id = http, case_id

    def _p(self, *parts):
        return "/cases/" + urllib.parse.quote(self.case_id, safe="") + "".join("/" + urllib.parse.quote(p, safe="") for p in parts)

    def list_case_documents(self, processing_status=None, limit=100, next_token=None):
        return self.http.get(self._p("documents"), {"processing_status": processing_status, "limit": limit, "next_token": next_token})

    def get_document(self, document_id):
        return self.http.get(self._p("documents", document_id))

    def get_document_vectors(self, document_id, similar_to_verified=3, include=None):
        return self.http.get(self._p("documents", document_id, "vectors"), {
            "include": include, "include_values": False, "similar_to_verified": similar_to_verified})

    def get_document_signatures(self, document_id, match_client=False):
        return self.http.get(self._p("documents", document_id, "signatures"), {
            "match_client": match_client, "include_vectors": False})


def list_all_documents(lister):
    """Projde stránkování (`lister(next_token) -> {documents, next_token}`)."""
    out, token = [], None
    for _ in range(100):
        page = lister(token)
        out.extend(page.get("documents", []))
        token = page.get("next_token")
        if not token:
            return out
    raise ApiError(0, "Seznam dokumentů má příliš mnoho stránek")


def documents_from_ingest(ingest_url, api_key, case_id, **kw):
    """`GET /cases/{case_id}/documents` z ingest API (jiná služba než agent API)."""
    http = HttpClient(ingest_url, api_key, **kw)
    path = "/cases/" + urllib.parse.quote(case_id, safe="") + "/documents"
    return list_all_documents(lambda tok: http.get(path, {"limit": 100, "next_token": tok}))


def documents_from_file(path):
    """Offline seznam: JSON ve tvaru odpovědi ingest API (`{"documents": [...]}`) nebo holé pole."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    docs = data.get("documents") if isinstance(data, dict) else data
    if not isinstance(docs, list):
        raise ValueError("Soubor se seznamem dokumentů musí obsahovat pole 'documents'")
    return docs
