"""HTTP evidence for the existing API. Read-only unless explicitly opted in.

Secrets live only in process memory. Never retries POST. Synthetic fixtures and
potential writes are reserved in the task-wide manifest before sending.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
import hashlib
from pathlib import Path
import sys
import threading
import time
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import build_opener, HTTPRedirectHandler, Request
from uuid import UUID, uuid4

import simplejson as json
from boto3.dynamodb.types import TypeSerializer

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
from case_client_test_deploy import (API, URL, CONFIG, BINDINGS, identity, session,
    FUNCTION, ROLE, load_manifest, save_manifest, reserve, require_writes, safe_error, UnexpectedHTTP)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def validate_url(url):
    if url != URL:
        raise ValueError('Unexpected HTTP target')


class Transport:
    def __init__(self, key, *, url=URL, clock=time.monotonic, sleep=time.sleep):
        validate_url(url)
        self.key = key
        self.url = url
        self.clock, self.sleep = clock, sleep
        self.lock = threading.Lock()
        self.slots = threading.BoundedSemaphore(2)
        self.next_start = 0
        self.deadline = clock() + 3600

    def request(self, method, path, query=None, body=None, auth='valid'):
        if not path.startswith('/') or '://' in path or '?' in path or '#' in path:
            raise ValueError('Invalid scoped path')
        with self.slots:
            with self.lock:
                now = self.clock()
                if now > self.deadline:
                    raise ValueError('HTTP deadline exhausted')
                self.sleep(max(0, self.next_start - now))
                now = self.clock()
                if now >= self.deadline:
                    raise ValueError('HTTP deadline exhausted')
                self.next_start = now + .55
            headers = {'Content-Type': 'application/json'}
            if auth != 'missing':
                headers['x-api-key'] = self.key if auth == 'valid' else 'invalid-offline-key'
            data = None if body is None else json.dumps(body, use_decimal=True).encode()
            target = self.url + path + ('?' + urlencode(query) if query else '')
            req = Request(target, data=data, headers=headers, method=method)
            try:
                remaining = self.deadline - self.clock()
                if remaining <= 0:
                    raise ValueError('HTTP deadline exhausted')
                response = build_opener(NoRedirect()).open(req, timeout=min(20, remaining))
            except HTTPError as error:
                response = error
            # No transport retry, including non-idempotent ambiguous timeouts.
            with response:
                raw = response.read(1024 * 1024)
                status = response.code
                backend = response.headers.get('X-Data-Backend')
            try:
                value = json.loads(raw, use_decimal=True)
            except ValueError:
                value = None
            return status, value, backend


def api_key(s):
    api = s.client('apigateway', config=CONFIG)
    plans = [p for page in api.get_paginator('get_usage_plans').paginate()
             for p in page.get('items', [])]
    for plan in plans:
        if not any(i['apiId'] == API and i['stage'] == 'v1' for i in plan.get('apiStages', [])):
            continue
        for page in api.get_paginator('get_usage_plan_keys').paginate(usagePlanId=plan['id']):
            for key in page.get('items', []):
                if key['id'] not in ('16u2jtkay6', 'b0w43mx5vf'):
                    continue
                detail = api.get_api_key(apiKey=key['id'], includeValue=True)
                if detail.get('enabled') and detail.get('value'):
                    return detail['value']
    raise ValueError('No enabled key for existing usage plan/stage')


def expect(http, method, path, status, **kwargs):
    actual, body, backend = http.request(method, path, **kwargs)
    if actual != status:
        raise UnexpectedHTTP(status, actual)
    if kwargs.get('auth', 'valid') == 'valid' and backend != 'dynamodb':
        raise AssertionError('Expected DynamoDB marker')
    return body


def scenario(m, name, operation):
    if m['scenarios'].get(name) == 'PASS':
        return
    try:
        operation()
    except Exception as error:
        m['scenarios'][name] = 'BLOCKED: ' + safe_error(error)
        save_manifest(m)
        raise
    m['scenarios'][name] = 'PASS'
    save_manifest(m)


def pages(http, path, key, query, maximum=80):
    items, seen = [], set()
    q = dict(query)
    for _ in range(maximum):
        body = expect(http, 'GET', path, 200, query=q)
        items.extend(body[key])
        token = body.get('next_token')
        if not token:
            return items
        if token in seen:
            raise AssertionError('Repeated pagination token')
        seen.add(token)
        q['next_token'] = token
    raise ValueError('Pagination budget exhausted')


def fixtures(s, m, run_id):
    if m.get('run_id') not in (None, run_id):
        raise ValueError('Task fixtures already belong to another run')
    m['run_id'] = run_id
    ddb = s.client('dynamodb', config=CONFIG)
    statuses = ['active', 'active', 'inactive', 'blocked']
    serializer = TypeSerializer()
    while len(m['fixtures']) < 4:
        identity(s)
        position = len(m['fixtures'])
        fixture = {'client_id': str(uuid4()), 'status': statuses[position],
                   'ico': str(90000000 + int(hashlib.sha256(
                       (run_id + str(position)).encode()).hexdigest()[:10], 16) % 9999999),
                   'name': f'Syntetický Žluťoučký {run_id} s.r.o.', 'source': 'synthetic'}
        # Reserve first: an ambiguous PutItem must never create a fifth client.
        m['fixtures'].append(fixture | {'state': 'reserved'})
        save_manifest(m)
        reserve(m, 'fixture_attempts', 4)
        ddb.put_item(TableName=BINDINGS['CLIENTS_TABLE_NAME'],
            Item={k: serializer.serialize(v) for k, v in fixture.items()},
            ConditionExpression='attribute_not_exists(client_id)')
        m['fixtures'][-1]['state'] = 'created'
        save_manifest(m)
    if any(f['state'] != 'created' for f in m['fixtures']):
        raise ValueError('Unverified fixture write')
    return m['fixtures']


def case_partition(s, client):
    """Scoped GSI count/IDs only, including nonexistent client's partition."""
    ddb = s.client('dynamodb', config=CONFIG)
    result = []
    for page in ddb.get_paginator('query').paginate(
            TableName=BINDINGS['CASES_TABLE_NAME'], IndexName=BINDINGS['CASES_CLIENT_CREATED_INDEX_NAME'],
            KeyConditionExpression='client_id = :c', ExpressionAttributeValues={':c': {'S': client}},
            ProjectionExpression='case_id', PaginationConfig={'MaxItems': 20, 'PageSize': 20}):
        result.extend(i['case_id']['S'] for i in page['Items'])
    return result


def write_matrix(s, http, m, run_id):
    fs = fixtures(s, m, run_id)
    active, other, inactive, blocked = [f['client_id'] for f in fs]
    missing = m.setdefault('missing_client_id', str(uuid4()))
    save_manifest(m)
    path = lambda c: f'/clients/{c}/cases'
    metadata = {'run_id': run_id, 'nested': {'amount': Decimal('123456789.123456789012345678'),
                'values': [None, True, Decimal('0.1000000000000000001')]}}
    ledger_lock = threading.Lock()

    def post(label, client, caller=None):
        label = m['suite_code_sha256'][:12] + '-' + label
        body = {'client_id': client, 'metadata': metadata | {'label': label}}
        if caller is not None:
            body['case_id'] = caller
        with ledger_lock:
            attempts = m.setdefault('posts', {})
            if label in attempts:
                if attempts[label].get('case_id'):
                    value = expect(http, 'GET', '/cases/' + attempts[label]['case_id'], 200)
                    validate_case(value, client, body, caller)
                    return value
                raise ValueError('Unverified prior POST: no retry')
            reserve(m, 'post_attempts', 12)
            attempts[label] = {'client_id': client, 'state': 'reserved'}
            save_manifest(m)
        try:
            value = expect(http, 'POST', '/cases', 201, body=body)
        except Exception:
            # Record potential write and reconcile only its fixture partition.
            # Cannot prove a 201 after losing the response; always BLOCKED.
            deadline = time.monotonic() + 60
            discovered = []
            while time.monotonic() < deadline:
                candidates = pages(http, path(client), 'cases', {'limit': '20'})
                discovered = [c['case_id'] for c in candidates
                    if c.get('metadata', {}).get('run_id') == run_id
                    and c.get('metadata', {}).get('label') == label]
                if discovered:
                    break
                time.sleep(2)
            with ledger_lock:
                attempts[label].update(state='ambiguous', discovered_ids=discovered)
                save_manifest(m)
            raise
        with ledger_lock:
            attempts[label].update(state='201', case_id=value['case_id'])
            m['case_ids'].append(value['case_id'])
            save_manifest(m)
        validate_case(value, client, body, caller)
        assert expect(http, 'GET', '/cases/' + value['case_id'], 200) == value
        return value

    def validate_case(value, client, body, caller):
        assert UUID(value['case_id']).version == 4 and value['case_id'] != caller
        assert value['client_id'] == client and value['status'] == 'open'
        assert value['metadata'] == body['metadata']

    def client_search():
        deadline = time.monotonic() + 60
        for f in fs:
            while True:
                values = pages(http, '/clients', 'clients', {'ico': f['ico'], 'limit': '1'})
                if f['client_id'] in {v['client_id'] for v in values}:
                    break
                if time.monotonic() >= deadline:
                    raise ValueError('ICO GSI propagation deadline')
                time.sleep(1)
        q = {'name': f'SYNTETICKY ZLUTOUCKY {run_id} společnost s ručením omezeným',
             'status': 'active', 'limit': '1'}
        found = pages(http, '/clients', 'clients', q)
        ids = [c['client_id'] for c in found]
        assert len(ids) == len(set(ids)) and set(ids) == {active, other}
        both = pages(http, '/clients', 'clients', {'ico': fs[0]['ico'], **q})
        assert {v['client_id'] for v in both} == {active}
        none = pages(http, '/clients', 'clients', {'ico': fs[0]['ico'], **q, 'status': 'blocked'})
        assert not none
        first = expect(http, 'GET', '/clients', 200, query=q)
        assert first.get('next_token')
        expect(http, 'GET', '/clients', 400, query={**q, 'status': 'inactive', 'next_token': first['next_token']})

    scenario(m, 'clients-search-normalization-and-pagination', client_search)

    def create_repeat():
        one = post('without-id-1', active)
        two = post('without-id-2', active)
        assert one['case_id'] != two['case_id']
    scenario(m, 'create-detail-decimal-repeat', create_repeat)

    def caller_ids():
        caller = 'synthetic-caller-' + run_id
        one = post('caller-active-1', active, caller)
        two = post('caller-active-2', other, caller)
        assert one['case_id'] != two['case_id']
    scenario(m, 'caller-id-ignored-cross-client', caller_ids)

    def concurrent():
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda label: post(label, active), ['concurrent-1', 'concurrent-2']))
        assert results[0]['case_id'] != results[1]['case_id']
    scenario(m, 'concurrent-posts-and-immediate-get', concurrent)

    def rejection():
        for client, status, label in [(missing, 404, 'unknown'), (inactive, 409, 'inactive'),
                                      (blocked, 409, 'blocked')]:
            assert not case_partition(s, client)
            reserve(m, 'post_attempts', 12)
            expect(http, 'POST', '/cases', status, body={'client_id': client,
                'metadata': {'run_id': run_id, 'label': label}})
        # Poll all negative partitions over a bounded propagation interval.
        until = time.monotonic() + 5
        while True:
            for client in (missing, inactive, blocked):
                assert not case_partition(s, client)
            if time.monotonic() >= until:
                break
            time.sleep(1)
        assert expect(http, 'GET', path(inactive), 200)['cases'] == []
        assert expect(http, 'GET', path(blocked), 200)['cases'] == []
        expect(http, 'GET', path(missing), 404)
    scenario(m, 'unknown-inactive-blocked-no-write', rejection)

    def case_pages():
        deadline = time.monotonic() + 60
        for client in (active, other):
            wanted = {p['case_id'] for p in m['posts'].values() if p['client_id'] == client and p.get('case_id')}
            while True:
                values = pages(http, path(client), 'cases', {'limit': '1'})
                ids = [c['case_id'] for c in values]
                if set(ids) == wanted:
                    break
                if time.monotonic() >= deadline:
                    raise ValueError('Cases GSI propagation deadline')
                time.sleep(1)
            assert len(ids) == len(set(ids))
            timestamps = [c['created_at'] for c in values]
            assert timestamps == sorted(timestamps, reverse=True)
        first = expect(http, 'GET', path(active), 200, query={'limit': '1'})
        token = first['next_token']
        assert token
        for endpoint, q in [(path(other), {'limit': '1'}), (path(active), {'limit': '2'}),
                            (path(active), {'limit': '1', 'status': 'open'})]:
            expect(http, 'GET', endpoint, 400, query={**q, 'next_token': token})
    scenario(m, 'case-pages-newest-first-query-bound', case_pages)


def run(args):
    s = session()
    identity(s)
    m = load_manifest()
    if args.allow_writes:
        require_writes(allow_writes=True, run_id=args.run_id)
    http = Transport(api_key(s))
    if 'live_started_at' in m:
        http.deadline = time.monotonic() + max(0, 3600 - (time.time() - m['live_started_at']))
    # Baseline applies to the original implementation, independent of backend.
    if args.baseline:
        assert http.request('GET', '/clients', {'limit': '1'}, auth='missing')[0] == 403
        assert http.request('GET', '/clients', {'limit': '1'}, auth='wrong')[0] == 403
        assert http.request('GET', '/clients', {'limit': '1'})[0] == 200
        m['original_http_baseline'] = 'PASS: auth 403/403 and protected GET 200'
        if m.get('rollback') == 'restored-code-and-config-awaiting-http':
            config = s.client('lambda', config=CONFIG).get_function_configuration(FunctionName=FUNCTION)
            if config['CodeSha256'] != m['original']['CodeSha256']:
                raise ValueError('Recovery smoke target hash mismatch')
            m['rollback'] = 'verified-code-config-and-http'
            m['recovery_http_smoke'] = 'PASS: auth 403/403 and protected GET 200'
        save_manifest(m)
        return

    config = s.client('lambda', config=CONFIG).get_function_configuration(FunctionName=FUNCTION)
    if (config['CodeSha256'] != m.get('artifact_code_sha256') or
            config['Runtime'] != 'python3.13' or config['Handler'] != 'case_client_handler.lambda_handler'
            or config['Role'] != ROLE or any(config.get('Environment', {}).get('Variables', {}).get(k) != v
                                           for k, v in BINDINGS.items())):
        raise ValueError('Live evidence requires our verified Python artifact/config')
    if m.get('suite_code_sha256') != config['CodeSha256']:
        m['scenarios'] = {}
    m['suite_code_sha256'] = config['CodeSha256']
    save_manifest(m)

    def auth():
        expect(http, 'GET', '/clients', 403, query={'limit': '1'}, auth='missing')
        expect(http, 'GET', '/clients', 403, query={'limit': '1'}, auth='wrong')
        expect(http, 'GET', '/clients', 200, query={'limit': '1'})
    scenario(m, 'auth', auth)

    def invalid():
        for query in ({'ico': 'bad'}, {'name': 'x'}, {'status': 'bad'}, {'limit': '0'},
                      {'limit': '101'}, {'limit': 'bad'}, {'next_token': 'bad!'}):
            expect(http, 'GET', '/clients', 400, query=query)
        expect(http, 'GET', '/cases/synthetic-missing-' + str(uuid4()), 404)
        missing = str(uuid4())
        expect(http, 'GET', f'/clients/{missing}/cases', 404)
        for query in ({'limit': '0'}, {'limit': '101'}, {'limit': 'bad'},
                      {'status': 'closed'}, {'next_token': 'bad!'}):
            expect(http, 'GET', f'/clients/{missing}/cases', 400, query=query)
    scenario(m, 'validation-and-missing', invalid)
    if args.allow_writes:
        identity(s)
        write_matrix(s, http, m, args.run_id)
        m['live_matrix'] = 'PASS'
    else:
        m['read_only_smoke'] = 'PASS (write matrix not executed)'
    save_manifest(m)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--allow-writes', action='store_true')
    parser.add_argument('--run-id', default='')
    parser.add_argument('--baseline', action='store_true')
    args = parser.parse_args()
    try:
        run(args)
        print(json.dumps({'result': 'PASS', 'mode': 'write-matrix' if args.allow_writes else 'read-only'}))
        return 0
    except Exception as error:
        m = load_manifest()
        m.update(status='BLOCKED', blocker=safe_error(error), blocked_action='http-integration')
        save_manifest(m)
        print(json.dumps({'result': 'BLOCKED', 'error': safe_error(error)}))
        return 1


if __name__ == '__main__':
    sys.exit(main())
