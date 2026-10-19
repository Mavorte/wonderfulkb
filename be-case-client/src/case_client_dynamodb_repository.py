"""External DynamoDB adapter. No table lifecycle, credentials or transport ownership."""
import base64
import binascii
from datetime import date, datetime, timezone
from decimal import Decimal, DecimalException
import hashlib
import json
import re
import time
from uuid import UUID

from boto3.dynamodb.types import TypeSerializer, TypeDeserializer

from case_client_repository import (InvalidRequest, NotFound, normalize_name,
                                    existing_case, active_client, metadata_json)

_SERIALIZER = TypeSerializer()
_DESERIALIZER = TypeDeserializer()
_CLIENT_FIELDS = {'client_id', 'ico', 'name', 'status', 'dic', 'legal_form', 'address', 'source'}
_NESTED = {'contacts': {'name': str, 'role': str, 'email': str, 'phone': str,
                        'preferred_channel': str},
           'signatories': {'name': str, 'function': str, 'authorized': bool},
           'kyc': {'status': str, 'checked_at': str}}


def _uuid(value):
    return isinstance(value, str) and bool(re.fullmatch(
        r'[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}', value)) and bool(UUID(value))


def _case_id(value):
    return isinstance(value, str) and bool(re.fullmatch(r'[A-Za-z0-9._-]{1,128}', value))


def _utc(value):
    if not isinstance(value, str) or not re.fullmatch(
            r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z', value):
        raise ValueError()
    datetime.fromisoformat(value.replace('Z', '+00:00'))


def _json_value(value, depth=0):
    """Reject DynamoDB-only types and numbers outside its exact decimal context."""
    if depth > 30:
        raise ValueError()
    if value is None or type(value) in (str, bool):
        return value
    if type(value) in (int, float) or isinstance(value, Decimal):
        # For direct Python callers, preserve the JSON float spelling rather
        # than converting its binary representation with Decimal(float).
        number = Decimal(str(value)) if type(value) is float else Decimal(value)
        if not number.is_finite() or (number and not -130 <= number.adjusted() <= 125):
            raise ValueError()
        _SERIALIZER.serialize(number)
        return number
    if isinstance(value, list):
        return [_json_value(item, depth + 1) for item in value]
    if isinstance(value, dict) and all(isinstance(k, str) for k in value):
        return {k: _json_value(item, depth + 1) for k, item in value.items()}
    raise ValueError()


def _metadata(value):
    try:
        metadata_json(value)
        result = _json_value(value)
        _SERIALIZER.serialize(result)
        return result
    except (ValueError, TypeError, DecimalException, RecursionError):
        raise InvalidRequest('Invalid metadata (limit: 16 KiB)') from None


def _decode(item, kind):
    """Validate public fields, ignore unverified internal attributes, invent no defaults."""
    try:
        fields = (_CLIENT_FIELDS | set(_NESTED) if kind == 'clients' else
                  {'case_id', 'client_id', 'status', 'created_at', 'metadata'})
        value = {k: _DESERIALIZER.deserialize(v) for k, v in item.items() if k in fields}
        if not _uuid(value['client_id']):
            raise ValueError()
        if kind == 'cases':
            if not _case_id(value['case_id']) or value['status'] != 'open':
                raise ValueError()
            _utc(value['created_at'])
            if 'metadata' in value:
                _metadata(value['metadata'])
        else:
            if not isinstance(value['ico'], str) or not re.fullmatch(r'[0-9]{8}', value['ico']):
                raise ValueError()
            if value['status'] not in ('active', 'inactive', 'blocked'):
                raise ValueError()
            if not isinstance(value['name'], str):
                raise ValueError()
            for key in _CLIENT_FIELDS - {'client_id', 'ico', 'name', 'status'}:
                if key in value and not isinstance(value[key], str):
                    raise ValueError()
            if 'source' in value and value['source'] != 'synthetic':
                raise ValueError()
            for key, types in _NESTED.items():
                if key not in value:
                    continue
                items = [value[key]] if key == 'kyc' else value[key]
                if not isinstance(items, list):
                    raise ValueError()
                public = []
                for entry in items:
                    if not isinstance(entry, dict):
                        raise ValueError()
                    entry = {k: v for k, v in entry.items() if k in types}
                    if any(type(v) is not types[k] for k, v in entry.items()):
                        raise ValueError()
                    if key == 'contacts' and entry.get('preferred_channel', 'email') not in ('email', 'phone'):
                        raise ValueError()
                    if key == 'contacts' and 'email' in entry and not re.fullmatch(r'[^@\s]+@[^@\s]+', entry['email']):
                        raise ValueError()
                    if key == 'kyc':
                        if entry.get('status', 'ok') not in ('ok', 'pending', 'failed'):
                            raise ValueError()
                        if 'checked_at' in entry:
                            if not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', entry['checked_at']):
                                raise ValueError()
                            date.fromisoformat(entry['checked_at'])
                    public.append(entry)
                value[key] = public[0] if key == 'kyc' else public
        return value
    except (KeyError, ValueError, TypeError, AttributeError, DecimalException, RecursionError):
        raise RuntimeError('Invalid stored data') from None


class DynamoDBCaseClientRepository:
    def __init__(self, sdk, *, clients_table, cases_table, clients_ico_index,
                 cases_client_created_index, region, clock=time.monotonic,
                 time_remaining=lambda: 7.0):
        self.sdk = sdk
        self.clients_table = clients_table
        self.cases_table = cases_table
        self.clients_ico_index = clients_ico_index
        self.cases_client_created_index = cases_client_created_index
        self.region = region
        self.clock = clock
        self.time_remaining = time_remaining

    def _get(self, kind, value):
        key = 'client_id' if kind == 'clients' else 'case_id'
        response = self.sdk.get_item(TableName=getattr(self, kind + '_table'),
            Key={key: {'S': value}}, ConsistentRead=True)
        return _decode(response['Item'], kind) if 'Item' in response else None

    def get_case(self, case_id):
        value = self._get('cases', case_id)
        if value is None:
            raise NotFound('Case not found')
        return value

    def _fingerprint(self, kind, client_id, filters, limit):
        return hashlib.sha256(json.dumps([
            'dynamodb', self.region, self.clients_table, self.cases_table,
            self.clients_ico_index, self.cases_client_created_index,
            kind, client_id, filters, limit], sort_keys=True,
            separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()

    def _key_fields(self, kind, filters):
        if kind == 'cases':
            return {'case_id', 'client_id', 'created_at'}
        return {'client_id', 'ico'} if 'ico' in filters else {'client_id'}

    def _cursor(self, token, fingerprint, fields):
        if token is None:
            return None
        try:
            if not isinstance(token, str) or not 1 <= len(token) <= 4096 or not re.fullmatch(r'[A-Za-z0-9_-]+', token):
                raise ValueError()
            raw = base64.b64decode(token + '=' * (-len(token) % 4), altchars=b'-_', validate=True)
            if base64.urlsafe_b64encode(raw).decode().rstrip('=') != token:
                raise ValueError()
            cursor = json.loads(raw)
            if not isinstance(cursor, dict) or set(cursor) != {'v', 'query', 'last'}:
                raise ValueError()
            if type(cursor['v']) is not int or cursor['v'] != 1 or cursor['query'] != fingerprint:
                raise ValueError()
            key = cursor['last']
            if not self._valid_key(key, fields):
                raise ValueError()
            return key
        except (ValueError, TypeError, UnicodeError, binascii.Error, RecursionError):
            raise InvalidRequest('Invalid next_token') from None

    @staticmethod
    def _valid_key(key, fields):
        return (isinstance(key, dict) and set(key) == fields and all(
            isinstance(v, dict) and set(v) == {'S'} and isinstance(v['S'], str)
            and 0 < len(v['S'].encode('utf-8')) <= 2048 for v in key.values()))

    def _token(self, key, fingerprint, fields):
        if not key:
            return None
        if not self._valid_key(key, fields):
            raise RuntimeError('Invalid database continuation')
        result = base64.urlsafe_b64encode(json.dumps(
            {'v': 1, 'query': fingerprint, 'last': key},
            separators=(',', ':')).encode()).decode().rstrip('=')
        if len(result) > 4096:
            raise RuntimeError('Invalid database continuation')
        return result

    def _list(self, kind, client_id, filters, limit, token):
        # Repository filters are canonicalized by the shared HTTP boundary,
        # exactly as for the mock. Normalization is not necessarily idempotent.
        filters = dict(filters)
        fingerprint = self._fingerprint(kind, client_id, filters, limit)
        fields = self._key_fields(kind, filters)
        start = self._cursor(token, fingerprint, fields)
        # Validate token first, even for a nonexistent client.
        deadline = self.clock() + min(7.0, max(0.0, self.time_remaining()))
        if kind == 'cases':
            if self.clock() + 3 > deadline:
                raise RuntimeError('Insufficient request budget')
            if self._get('clients', client_id) is None:
                raise NotFound('Client not found')
        params = {'TableName': getattr(self, kind + '_table')}
        operation = 'scan'
        if kind == 'cases':
            operation = 'query'
            params.update(IndexName=self.cases_client_created_index,
                KeyConditionExpression='#client = :client',
                ExpressionAttributeNames={'#client': 'client_id'},
                ExpressionAttributeValues={':client': {'S': client_id}}, ScanIndexForward=False)
        elif 'ico' in filters:
            operation = 'query'
            params.update(IndexName=self.clients_ico_index,
                KeyConditionExpression='#ico = :ico', ExpressionAttributeNames={'#ico': 'ico'},
                ExpressionAttributeValues={':ico': {'S': filters['ico']}})
        if start:
            params['ExclusiveStartKey'] = start
        pages = iter(self.sdk.get_paginator(operation).paginate(
            **params, PaginationConfig={'PageSize': min(limit, 25)}))
        selected, continuation = [], start
        for _ in range(8):
            if self.clock() + 3 > deadline:
                # No first-page position exists to truthfully resume without a read.
                if continuation is None:
                    raise RuntimeError('Insufficient request budget')
                break
            page = next(pages)
            items = page.get('Items', [])
            continuation = page.get('LastEvaluatedKey') or None
            for index, item in enumerate(items):
                value = _decode(item, kind)
                if all((normalize_name(value['name']).find(v) >= 0 if k == 'name'
                        else value[k] == v) for k, v in filters.items()):
                    selected.append(value)
                if len(selected) == limit:
                    if index < len(items) - 1:
                        continuation = {k: item[k] for k in fields}
                    break
            if len(selected) == limit or continuation is None:
                break
        return {kind: selected, 'next_token': self._token(continuation, fingerprint, fields)}

    def list_clients(self, filters, limit, token=None):
        return self._list('clients', None, filters, limit, token)

    def list_client_cases(self, client_id, filters, limit, token=None):
        return dict(self._list('cases', client_id, filters, limit, token), client_id=client_id)

    def create_case(self, case_id, client_id, metadata):
        metadata = _metadata(metadata)
        if not _case_id(case_id) or not _uuid(client_id):
            raise InvalidRequest('Invalid case or client ID')
        old = self._get('cases', case_id)
        if old is not None:
            return existing_case(old, client_id)
        active_client(self._get('clients', client_id))
        value = {'case_id': case_id, 'client_id': client_id, 'status': 'open',
                 'created_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%fZ'),
                 'metadata': metadata}
        item = _SERIALIZER.serialize(value)['M']
        try:
            self.sdk.transact_write_items(TransactItems=[
                {'ConditionCheck': {'TableName': self.clients_table,
                    'Key': {'client_id': {'S': client_id}},
                    'ConditionExpression': 'attribute_exists(#id) AND #status = :active',
                    'ExpressionAttributeNames': {'#id': 'client_id', '#status': 'status'},
                    'ExpressionAttributeValues': {':active': {'S': 'active'}}}},
                {'Put': {'TableName': self.cases_table, 'Item': item,
                    'ConditionExpression': 'attribute_not_exists(#id)',
                    'ExpressionAttributeNames': {'#id': 'case_id'}}}])
        except self.sdk.exceptions.TransactionCanceledException as error:
            reasons = error.response.get('CancellationReasons', [])
            codes = [r.get('Code') for r in reasons]
            if (len(codes) != 2 or 'ConditionalCheckFailed' not in codes
                    or any(c not in ('None', 'ConditionalCheckFailed') for c in codes)):
                raise
            winner = self._get('cases', case_id)
            if winner is not None:
                return existing_case(winner, client_id)
            active_client(self._get('clients', client_id))
            raise RuntimeError('Unresolved transaction condition') from None
        return _decode(item, 'cases'), True
