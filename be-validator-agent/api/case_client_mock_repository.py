"""Synthetic, instance-local data. Never a durable or shared database."""
import base64
import binascii
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from threading import Lock
from uuid import uuid4

from case_client_repository import CASE_STATUSES, InvalidRequest, NotFound, normalize_name, active_client


def _page(items, id_field, scope, filters, limit, token):
    fingerprint = hashlib.sha256(json.dumps(
        [scope, filters, limit], sort_keys=True, ensure_ascii=False,
        separators=(',', ':')).encode('utf-8')).hexdigest()
    start = 0
    if token is not None:
        try:
            if not isinstance(token, str) or not 1 <= len(token) <= 4096:
                raise ValueError()
            if not re.fullmatch(r'[A-Za-z0-9_-]+', token):
                raise ValueError()
            raw = base64.b64decode(token + '=' * (-len(token) % 4),
                                   altchars=b'-_', validate=True)
            if base64.urlsafe_b64encode(raw).decode().rstrip('=') != token:
                raise ValueError()
            cursor = json.loads(raw.decode('utf-8'))
            if not isinstance(cursor, dict) or set(cursor) != {'v', 'query', 'last'}:
                raise ValueError()
            if type(cursor['v']) is not int or cursor['v'] != 1:
                raise ValueError()
            if cursor['query'] != fingerprint or not isinstance(cursor['last'], str):
                raise ValueError()
            start = next(i + 1 for i, item in enumerate(items)
                         if item[id_field] == cursor['last'])
        except (ValueError, TypeError, StopIteration, UnicodeError, binascii.Error, RecursionError):
            raise InvalidRequest('Invalid next_token') from None
    selected = items[start:start + limit]
    next_token = None
    if start + limit < len(items):
        cursor = {'v': 1, 'query': fingerprint, 'last': selected[-1][id_field]}
        next_token = base64.urlsafe_b64encode(json.dumps(
            cursor, separators=(',', ':')).encode()).decode().rstrip('=')
    return deepcopy(selected), next_token


class MockCaseClientRepository:
    def __init__(self):
        fixtures = deepcopy(json.loads(Path(__file__).with_name(
            'case_client_fixtures.json').read_text(encoding='utf-8')))
        self._clients = {c['client_id']: c for c in fixtures['clients']}
        self._cases = {c['case_id']: c for c in fixtures['cases']}
        self._lock = Lock()

    def list_clients(self, filters, limit, token=None):
        with self._lock:
            items = [client for client in self._clients.values()
                     if all((normalize_name(client['name']).find(value) >= 0
                             if key == 'name' else client[key] == value)
                            for key, value in filters.items())]
            items.sort(key=lambda c: c['client_id'])
            clients, next_token = _page(items, 'client_id', 'clients', filters, limit, token)
            return {'clients': clients, 'next_token': next_token}

    def create_case(self, client_id, metadata):
        with self._lock:
            active_client(self._clients.get(client_id))
            for _ in range(3):
                case_id = str(uuid4())
                if case_id not in self._cases:
                    break
            else:
                raise RuntimeError('Unable to allocate case ID')
            case = {'case_id': case_id, 'client_id': client_id, 'status': 'open',
                    'created_at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                    'metadata': deepcopy(metadata)}
            self._cases[case_id] = case
            return deepcopy(case)

    def get_case(self, case_id):
        with self._lock:
            if case_id not in self._cases:
                raise NotFound('Case not found')
            return deepcopy(self._cases[case_id])

    def list_cases(self, filters, limit, token=None):
        with self._lock:
            items = [c for c in self._cases.values() if all(c[k] == v for k, v in filters.items())]
            items.sort(key=lambda c: c['case_id'])
            cases, next_token = _page(items, 'case_id', 'global-cases', filters, limit, token)
            return {'cases': cases, 'next_token': next_token}

    def list_client_cases(self, client_id, filters, limit, token=None):
        with self._lock:
            if client_id not in self._clients:
                raise NotFound('Client not found')
            items = [c for c in self._cases.values() if c['client_id'] == client_id
                     and all(c[k] == v for k, v in filters.items())]
            items.sort(key=lambda c: (-datetime.fromisoformat(c['created_at'].replace(
                'Z', '+00:00')).timestamp(), c['case_id']))
            cases, next_token = _page(items, 'case_id', ['client-cases', client_id],
                                     filters, limit, token)
            return {'client_id': client_id, 'cases': cases, 'next_token': next_token}

    def set_case_status(self, case_id, status):
        if status not in CASE_STATUSES:
            raise InvalidRequest('Invalid status')
        with self._lock:
            if case_id not in self._cases:
                raise NotFound('Case not found')
            self._cases[case_id].update(status=status, status_updated_at=datetime.now(
                timezone.utc).isoformat().replace('+00:00', 'Z'))
            return deepcopy(self._cases[case_id])
