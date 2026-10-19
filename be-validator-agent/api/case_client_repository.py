"""The four-operation persistence boundary; no transport or AWS dependency."""
from typing import Protocol
import re
import unicodedata
import simplejson as json


class InvalidRequest(ValueError):
    pass


class NotFound(Exception):
    pass


class Conflict(Exception):
    pass


def normalize_name(value):
    value = ''.join(c for c in unicodedata.normalize('NFKD', value.casefold())
                    if not unicodedata.combining(c))
    value = re.sub(
        r'(?<!\w)(?:spolecnost\s+s\s+rucenim\s+omezenym|akciova\s+spolecnost|'
        r's\s*\.?\s*r\s*\.?\s*o\.?|a\s*\.?\s*s\.?|'
        r'v\s*\.?\s*o\s*\.?\s*s\.?|k\s*\.?\s*s\.?)(?!\w)', ' ', value)
    return ' '.join(value.split())


def existing_case(case, client_id):
    if case['client_id'] != client_id:
        raise Conflict('Case belongs to another client')
    return case, False


def active_client(client):
    if client is None:
        raise NotFound('Client not found')
    if client['status'] != 'active':
        raise Conflict('Client is not active')


def metadata_json(metadata):
    """One compact UTF-8 size rule for both backends and direct adapter calls."""
    try:
        if not isinstance(metadata, dict):
            raise ValueError()
        value = json.dumps(metadata, ensure_ascii=False, separators=(',', ':'),
                           allow_nan=False, use_decimal=True)
        if len(value.encode('utf-8')) > 16384:
            raise ValueError()
        return value
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise InvalidRequest('Invalid metadata (limit: 16 KiB)') from None


class CaseClientRepository(Protocol):
    def list_clients(self, filters: dict, limit: int, token: str = None) -> dict: ...

    def create_case(self, client_id: str, metadata: dict) -> dict: ...

    def get_case(self, case_id: str) -> dict: ...

    def list_cases(self, filters: dict, limit: int, token: str = None) -> dict: ...

    def list_client_cases(self, client_id: str, filters: dict,
                          limit: int, token: str = None) -> dict: ...
