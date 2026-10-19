"""Zdroje dat pro evaluaci: HTTP (nasazené API nebo mock), lokální handler API, mock v procesu.

Každý transport má `get(path, query) -> Result`. API klíč se drží jen v hlavičce požadavku; nikdy se nevypisuje,
neukládá do reportu a nevstupuje do chybových zpráv (u chyb se uchovává jen třída výjimky).
"""
import json
import os
import secrets
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Optional

_BASE = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))  # validator-agent / be-validator-agent
REPO = os.path.abspath(os.path.join(_BASE, "..", ".."))
API_DIR = os.path.join(_BASE, "api")
# repo: be-validator-agent/mock; pracovní kopie: infra/validator-agent-mock
MOCK_DIR = next((p for p in (os.path.join(_BASE, "mock"), os.path.join(_BASE, "..", "validator-agent-mock")) if os.path.isdir(p)),
                os.path.join(_BASE, "mock"))


@dataclass
class Result:
    status: Optional[int]          # HTTP status; None = bez odpovědi (síť, časový limit)
    body: Any = None
    ms: float = 0.0                # trvání posledního pokusu
    error: Optional[str] = None    # jen třída chyby, např. "timeout", "URLError"
    attempts: int = 1
    simulated: bool = False
    meta: dict = field(default_factory=dict)


def _clean_query(query):
    return {k: ("true" if v is True else "false" if v is False else v) for k, v in (query or {}).items()
            if v is not None}


class Transport:
    """Základ: opakování při 5xx a chybách sítě (volání jsou idempotentní)."""

    mode = "?"
    host = None

    def __init__(self, retries=0, backoff=0.5):
        self.retries, self.backoff = retries, backoff

    def _once(self, path, query):
        raise NotImplementedError

    def get(self, path, query=None):
        query = _clean_query(query)
        res = None
        for attempt in range(1, self.retries + 2):
            res = self._once(path, query)
            res.attempts = attempt
            if res.status is not None and res.status < 500:
                return res
            if attempt <= self.retries:
                time.sleep(self.backoff * attempt)
        return res


class HttpTransport(Transport):
    mode = "http"

    def __init__(self, base_url, api_key, timeout=30.0, retries=0, backoff=0.5):
        super().__init__(retries, backoff)
        self.base = base_url.rstrip("/")
        self._key = api_key
        self.timeout = timeout
        p = urllib.parse.urlparse(self.base)
        self.host = p.netloc or None

    def _once(self, path, query):
        url = self.base + path + (("?" + urllib.parse.urlencode(query)) if query else "")
        req = urllib.request.Request(url, headers={"x-api-key": self._key, "Accept": "application/json"})
        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                raw = r.read()
                status = r.status
        except urllib.error.HTTPError as e:
            raw, status = e.read(), e.code
        except TimeoutError:
            return Result(None, None, (time.perf_counter() - t0) * 1000, "timeout")
        except urllib.error.URLError as e:
            kind = "timeout" if isinstance(getattr(e, "reason", None), TimeoutError) else "URLError"
            return Result(None, None, (time.perf_counter() - t0) * 1000, kind)
        except Exception as e:  # noqa: BLE001
            return Result(None, None, (time.perf_counter() - t0) * 1000, type(e).__name__)
        ms = (time.perf_counter() - t0) * 1000
        try:
            body = json.loads(raw.decode("utf-8")) if raw else None
        except ValueError:
            return Result(status, None, ms, "invalid_json")
        return Result(status, body, ms)


class LocalTransport(Transport):
    """Volá `core.handle` z infra/validator-agent/api přímo v procesu (bez HTTP).

    Klíč je jednorázový náhodný řetězec nastavený do `API_KEY` před vytvořením `core.Api()`, takže se nečte
    Secrets Manager a nic se nikam nevypisuje. Data čte ze skutečných úložišť (profil z `AWS_PROFILE`), nebo
    z moto fixtur s `fixtures=True`.
    """

    mode = "local-handler"

    def __init__(self, fixtures=False, retries=0, backoff=0.5):
        super().__init__(retries, backoff)
        if API_DIR not in sys.path:
            sys.path.insert(0, API_DIR)
        self._key = secrets.token_hex(16)
        os.environ["API_KEY"] = self._key
        self.index = None
        self._moto = None
        if fixtures:
            from moto import mock_aws
            self._moto = mock_aws()
            self._moto.start()
            import fixtures as fx  # api/fixtures.py
            self.api, self.index, _ = fx.build(self._key)
            self.mode = "local-handler-fixtures"
        else:
            import core
            self.api = core.Api()
        import core
        self._core = core

    def close(self):
        if self._moto:
            self._moto.stop()

    def _once(self, path, query):
        t0 = time.perf_counter()
        try:
            status, body = self._core.handle("GET", "/v1" + path, query, {"x-api-key": self._key}, api=self.api)
        except Exception as e:  # noqa: BLE001
            return Result(None, None, (time.perf_counter() - t0) * 1000, type(e).__name__)
        # tělo projde stejnou serializací jako v Lambdě (Decimal apod.)
        body = json.loads(self._core.dumps(body).decode("utf-8"))
        return Result(status, body, (time.perf_counter() - t0) * 1000)


class MockServer:
    """Spustí mock z infra/validator-agent-mock v procesu na volném portu a vrátí HttpTransport."""

    def __init__(self, texts_dir=None):
        self.api_key = "mock-" + secrets.token_hex(8)
        os.environ["API_KEY"] = self.api_key
        os.environ["QUIET"] = "1"
        if texts_dir:
            os.environ["TEXT_DIR"] = texts_dir
        if MOCK_DIR not in sys.path:
            sys.path.insert(0, MOCK_DIR)
        import importlib
        import server as mock_server  # infra/validator-agent-mock/server.py
        importlib.reload(mock_server)
        from http.server import ThreadingHTTPServer
        self.module = mock_server
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), mock_server.Handler)
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    @property
    def base_url(self):
        return f"http://127.0.0.1:{self.port}/v1"

    def transport(self, timeout=30.0, retries=0):
        t = HttpTransport(self.base_url, self.api_key, timeout=timeout, retries=retries)
        t.mode = "mock"
        return t

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()
