"""Single API Gateway REST proxy handler for explicit mock or DynamoDB mode."""
import base64
import binascii
import simplejson as json
import os
import re
from threading import Lock
from uuid import UUID
from contextvars import ContextVar

from case_client_repository import (CaseClientRepository, Conflict, InvalidRequest, NotFound,
                                    normalize_name, metadata_json)
from case_client_mock_repository import MockCaseClientRepository

_request_context = ContextVar('case_client_request_context', default=None)


def _remaining():
    context = _request_context.get()
    return max(0, context.get_remaining_time_in_millis() / 1000 - 1) if context else 7.0

CLIENT_FIELDS = {'client_id', 'ico', 'dic', 'name', 'legal_form', 'address', 'status', 'source'}
CASE_FIELDS = {'case_id', 'client_id', 'status', 'created_at', 'metadata'}
NESTED_FIELDS = {'contacts': {'name', 'role', 'email', 'phone', 'preferred_channel'},
                 'signatories': {'name', 'function', 'authorized'},
                 'kyc': {'status', 'checked_at'}}


def _public_client(client):
    result = {k: v for k, v in client.items() if k in CLIENT_FIELDS}
    for key, fields in NESTED_FIELDS.items():
        if key in client:
            items = client[key]
            if key == 'kyc':
                result[key] = {k: v for k, v in items.items() if k in fields}
            else:
                result[key] = [{k: v for k, v in item.items() if k in fields} for item in items]
    return result


def _public_case(case):
    return {k: v for k, v in case.items() if k in CASE_FIELDS}


def _configured():
    backend = os.environ.get('DATA_BACKEND')
    if backend == 'mock' and os.environ.get('ALLOW_EPHEMERAL_MOCK') == 'true':
        return backend, {}
    if backend != 'dynamodb':
        raise RuntimeError('Explicit valid backend configuration required')
    config = {}
    for env, key in (('CLIENTS_TABLE_NAME', 'clients_table'), ('CASES_TABLE_NAME', 'cases_table'),
                     ('CLIENTS_ICO_INDEX_NAME', 'clients_ico_index'),
                     ('CASES_CLIENT_CREATED_INDEX_NAME', 'cases_client_created_index')):
        value = os.environ.get(env, '')
        if not re.fullmatch(r'[A-Za-z0-9_.-]{3,255}', value):
            raise RuntimeError('Invalid database configuration')
        config[key] = value
    if config['clients_table'] == config['cases_table']:
        raise RuntimeError('Distinct database tables required')
    region = os.environ.get('AWS_REGION') or os.environ.get('AWS_DEFAULT_REGION', '')
    if not re.fullmatch(r'[a-z]{2}(?:-[a-z]+)+-[0-9]+', region):
        raise RuntimeError('Invalid database region')
    config['region'] = region
    return backend, config


def _response(status, data, backend='mock'):
    headers = {'Content-Type': 'application/json'}
    if backend:
        headers['X-Data-Backend'] = backend
    return {'statusCode': status, 'headers': headers,
            'body': json.dumps(data, ensure_ascii=False, allow_nan=False, use_decimal=True)}


def _case_id(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9._-]{1,128}', value):
        raise InvalidRequest('Invalid case_id')
    return value


def _client_id(value):
    if not isinstance(value, str) or not re.fullmatch(
            r'[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}', value):
        raise InvalidRequest('Invalid client_id UUID')
    return str(UUID(value))


def _query(event, clients=False):
    query = event.get('queryStringParameters')
    query = {} if query is None else query
    if not isinstance(query, dict) or any(not isinstance(v, str) for v in query.values()):
        raise InvalidRequest('Query values must be strings')
    value = query.get('limit', '50')
    if not re.fullmatch(r'[0-9]+', value) or len(value) > 3 or not 1 <= int(value) <= 100:
        raise InvalidRequest('limit must be an integer from 1 to 100')
    filters = {}
    if 'status' in query:
        statuses = {'active', 'inactive', 'blocked'} if clients else {'open'}
        if query['status'] not in statuses:
            raise InvalidRequest('Invalid status')
        filters['status'] = query['status']
    if clients and 'ico' in query:
        if not re.fullmatch(r'[0-9]{8}', query['ico']):
            raise InvalidRequest('ico must contain eight digits')
        filters['ico'] = query['ico']
    if clients and 'name' in query:
        name = query['name']
        normalized = normalize_name(name)
        if not 2 <= len(name) <= 255 or not normalized:
            raise InvalidRequest('Invalid name filter')
        filters['name'] = normalized
    return filters, int(value), query.get('next_token')


def _reject_constant(value):
    raise ValueError('Nonstandard JSON constant')


def _request(event):
    try:
        raw = event.get('body')
        if event.get('isBase64Encoded', False):
            raw = base64.b64decode(raw, validate=True).decode('utf-8')
        if not isinstance(raw, str):
            raise ValueError()
        body = json.loads(raw, parse_constant=_reject_constant, use_decimal=True)
        if not isinstance(body, dict):
            raise ValueError()
        _case_id(body.get('case_id'))
        client_id = _client_id(body.get('client_id'))
        metadata = body.get('metadata', {})
        if not isinstance(metadata, dict):
            raise ValueError()
        metadata_json(metadata)
        return body['case_id'], client_id, metadata
    except (ValueError, TypeError, UnicodeError, binascii.Error, RecursionError):
        raise InvalidRequest('Invalid JSON request or fields (metadata limit: 16 KiB)') from None


def _route(event):
    resource = event.get('resource') or event.get('path', '')
    params = event.get('pathParameters') or {}
    if resource in ('/clients', '/cases', '/cases/{case_id}', '/clients/{client_id}/cases'):
        return resource, params
    match = re.fullmatch(r'/cases/([^/]+)', resource)
    if match:
        return '/cases/{case_id}', {'case_id': match[1]}
    match = re.fullmatch(r'/clients/([^/]+)/cases', resource)
    if match:
        return '/clients/{client_id}/cases', {'client_id': match[1]}
    return None, {}


def create_handler(repository: CaseClientRepository = None):
    backend, config = _configured()
    if repository is None:
        if backend == 'mock':
            repository = MockCaseClientRepository()
        else:
            import boto3
            from botocore.config import Config
            from case_client_dynamodb_repository import DynamoDBCaseClientRepository
            sdk = boto3.client('dynamodb', region_name=config['region'], config=Config(
                connect_timeout=1, read_timeout=2, retries={'total_max_attempts': 1}))
            repository = DynamoDBCaseClientRepository(sdk, **config, time_remaining=_remaining)

    def response(status, data):
        return _response(status, data, backend)

    def handler(event, context):
        context_token = _request_context.set(context)
        try:
            route, params = _route(event)
            if route is None:
                return response(404, {'error': 'Route not found'})
            method = 'POST' if route == '/cases' else 'GET'
            if event.get('httpMethod') != method:
                return response(405, {'error': 'Method not allowed'})
            if route == '/clients':
                data = repository.list_clients(*_query(event, clients=True))
                data['clients'] = [_public_client(c) for c in data['clients']]
            elif route == '/cases':
                case, created = repository.create_case(*_request(event))
                return response(201 if created else 200, _public_case(case))
            elif route == '/cases/{case_id}':
                data = _public_case(repository.get_case(_case_id(params.get('case_id'))))
            else:
                data = repository.list_client_cases(_client_id(params.get('client_id')), *_query(event))
                data['cases'] = [_public_case(c) for c in data['cases']]
            return response(200, data)
        except InvalidRequest as error:
            return response(400, {'error': str(error)})
        except NotFound as error:
            return response(404, {'error': str(error)})
        except Conflict as error:
            return response(409, {'error': str(error)})
        except Exception:
            return response(500, {'error': 'Internal service error'})
        finally:
            _request_context.reset(context_token)
    return handler


_cached_handler = None
_cached_configuration = None
_initialization_lock = Lock()


def lambda_handler(event, context):
    global _cached_handler, _cached_configuration
    try:
        configuration = _configured()
        with _initialization_lock:
            if _cached_handler is None or _cached_configuration != configuration:
                _cached_handler = create_handler()
                _cached_configuration = configuration
        return _cached_handler(event, context)
    except Exception:
        return _response(500, {'error': 'Service configuration or initialization failed'}, backend=None)
