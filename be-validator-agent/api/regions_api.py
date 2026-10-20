"""Regiony dokumentu (odstavce s polohou, textem a štítkem) z `analysis/<document_id>/regions.json`.

Dvě cesty, obě GET za stejnou kontrolou x-api-key jako zbytek API (`core.authorize`); směruje je `app.handler`
(a lokální `server.py`), `core.py` se nemění:

- `/cases/{case_id}/regions?label=&party=&kind=&q=` regiony napříč všemi dokumenty případu (porovnání stran,
  hledání povinných podkladů). Bez aspoň jednoho filtru 400, aby agent nestahoval celý případ.
- `/cases/{case_id}/documents/{document_id}/regions?outline=&ids=&page=&label=&party=&kind=&q=&include_geometry=`
  regiony jednoho dokumentu: přehled (`outline=true`), vybrané regiony (`ids=`) nebo vše; geometrie (`bbox`,
  `lines`) pro UI, agent ji vypíná.

Tvar souboru: be-validator-agent/regions/README.md, návrh: be-validator-agent/docs/regiony-dokumentu-navrh.md.
"""
from __future__ import annotations

import json
import logging
import re
import unicodedata

import core
from core import ApiError

log = logging.getLogger("wonderfulkb.agent_api")

CASE_RX = re.compile(r"^/cases/([^/]+)/regions$")
DOCUMENT_RX = re.compile(r"^/cases/([^/]+)/documents/([^/]+)/regions$")
EXCERPT = 80
MAX_IDS = 200
FILTERS = ("label", "party", "kind")


def matches(path):
    return bool(CASE_RX.match(path) or DOCUMENT_RX.match(path))


def _fold(text):
    text = unicodedata.normalize("NFKD", text or "")
    return re.sub(r"\s+", " ", "".join(c for c in text if not unicodedata.combining(c))).strip().lower()


def _csv(query, name):
    raw = core._q1(query, name)
    if raw is None:
        return None
    values = {v.strip() for v in raw.split(",") if v.strip()}
    if not values or any(len(v) > 64 for v in values):
        raise ApiError(400, f"Neplatný parametr {name}")
    return values


def _filters(query):
    out = {name: _csv(query, name) for name in FILTERS}
    q = core._q1(query, "q")
    if q is not None and not (1 <= len(q.strip()) <= 200):
        raise ApiError(400, "Neplatný parametr q")
    out["q"] = _fold(q) if q else None
    out["page"] = core._int(query, "page", 1, 10000)
    return out


def _keep(region, f):
    if f["page"] is not None and region.get("page") != f["page"]:
        return False
    for name in FILTERS:
        if f[name] is not None and region.get(name) not in f[name]:
            return False
    return f["q"] is None or f["q"] in _fold(region.get("text"))


def _shape(region, outline, geometry):
    """Region pro odpověď. Přehled: bez textu a souřadnic, jen začátek textu (levné na tokeny)."""
    base = {k: region.get(k) for k in ("region_id", "page", "kind", "label", "party", "refers_to", "summary")}
    base = {k: v for k, v in base.items() if v is not None}
    text = region.get("text") or ""
    if outline:
        base["excerpt"] = text if len(text) <= EXCERPT else text[:EXCERPT] + "…"
        return base
    base["section"] = region.get("section")
    base["text"] = text
    if geometry:
        base["bbox"] = region.get("bbox")
        base["lines"] = region.get("lines") or []
    return base


class Regions:
    def __init__(self, api):
        self.api = api
        self.repo = api.repo

    def _key(self, row, case_id, document_id):
        return row.get("regions_s3_key") or f"cases/{case_id}/analysis/{document_id}/regions.json"

    def _load(self, row, case_id, document_id):
        """(status, body): completed + obsah, not_run (soubor není: dokument se na regiony nezpracoval, prázdný
        seznam NENÍ důkaz, že tam nic není), nebo failed (soubor je, ale nejde přečíst)."""
        if not core._ok_status(row):
            return "not_ready", None
        key = self._key(row, case_id, document_id)
        if not self.repo.object_exists(key):
            return "not_run", None
        try:
            body = json.loads(self.repo.read_object(key).decode("utf-8"))
            if not isinstance(body, dict) or not isinstance(body.get("regions"), list):
                raise ValueError("regions není seznam")
            return "completed", body
        except (ValueError, UnicodeDecodeError) as error:
            log.warning("regions.json %s/%s nejde přečíst: %s", case_id, document_id, error)
            return "failed", None

    # GET /cases/{case_id}/documents/{document_id}/regions
    def document(self, case_id, document_id, query):
        row = self.api._row(case_id, document_id)  # 404 neznámý, 409 jen v ingestu (stejně jako ostatní volání)
        outline = core._bool(query, "outline", False)
        geometry = core._bool(query, "include_geometry", True) and not outline
        ids = _csv(query, "ids")
        if ids is not None and len(ids) > MAX_IDS:
            raise ApiError(400, f"Nejvýš {MAX_IDS} id najednou")
        f = _filters(query)
        status, body = self._load(row, case_id, document_id)
        out = {"case_id": case_id, "document_id": document_id, "title": row.get("title", ""),
               "document_label": row.get("label"), "status": status, "pages": [], "regions": []}
        if status == "not_ready":
            out["processing_status"] = row.get("processing_status")
        if body is None:
            return out
        regions = [r for r in body["regions"] if isinstance(r, dict) and _keep(r, f)
                   and (ids is None or r.get("region_id") in ids)]
        out["pages"] = body.get("pages") or []
        out["regions"] = [_shape(r, outline, geometry) for r in regions]
        if ids is not None:
            found = {r.get("region_id") for r in regions}
            out["missing_ids"] = sorted(ids - found)
        return out

    # GET /cases/{case_id}/regions
    def case(self, case_id, query):
        core._ids(case_id)
        f = _filters(query)
        if not any(f[name] for name in (*FILTERS, "q")):
            raise ApiError(400, "Zadejte aspoň jeden filtr: label, party, kind nebo q")
        outline = core._bool(query, "outline", False)
        geometry = core._bool(query, "include_geometry", False) and not outline
        rows = self.repo.query_rows(case_id, None, 10**6, None)[0]
        if not rows and not self.repo.case_exists(case_id):
            raise ApiError(404, "Case neexistuje")
        found, without = [], []
        for summary in sorted(rows, key=lambda r: r["document_id"]):
            document_id = summary["document_id"]
            row = self.repo.get_row(case_id, document_id) or summary  # query_rows nevrací regions_s3_key
            status, body = self._load(row, case_id, document_id)
            if body is None:
                without.append({"document_id": document_id, "title": row.get("title", ""), "status": status})
                continue
            for region in body["regions"]:
                if isinstance(region, dict) and _keep(region, f):
                    found.append({"document_id": document_id, "title": row.get("title", ""),
                                  "document_label": row.get("label"), **_shape(region, outline, geometry)})
        return {"case_id": case_id, "regions": found, "documents_without_regions": without}


def handle(method, path, query=None, headers=None, api=None):
    """(status, body) pro cesty regionů; `path` bez prefixu /v1."""
    if api is None:
        if core._default is None:
            core._default = core.Api()
        api = core._default
    denied = core.authorize(headers, api)
    if denied:
        return denied
    query = query or {}
    try:
        if method.upper() != "GET":
            raise ApiError(405, "Povolena je jen metoda GET")
        regions = Regions(api)
        m = DOCUMENT_RX.match(path)
        if m:
            return 200, regions.document(*m.groups(), query)
        m = CASE_RX.match(path)
        if m:
            return 200, regions.case(m.group(1), query)
        raise ApiError(404, "Neznámá cesta")
    except ApiError as e:
        return e.status, {"error": e.msg, **e.extra}
    except Exception:  # noqa: BLE001
        log.exception("Neošetřená chyba")
        return 500, {"error": "Interní chyba služby"}
