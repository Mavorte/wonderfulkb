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

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
from case_client_test_deploy import (API, URL, CONFIG, BINDINGS, identity, session,
    FUNCTION, ROLE, ROOT, LEDGER_LOCK, CONTINUATION, exclusive_run, validate_ledger,
    load_manifest, save_manifest, require_writes, safe_error, UnexpectedHTTP, binding_readback, fingerprint)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def validate_url(url):
    if url != URL:
        raise ValueError('Unexpected HTTP target')


class Transport:
    def __init__(self, key, *, manifest=None, url=URL, clock=time.monotonic, sleep=time.sleep):
        validate_url(url)
        self.key = key
        self.manifest = manifest
        self.url = url
        self.clock, self.sleep = clock, sleep
        self.lock = threading.Lock()
        self.slots = threading.BoundedSemaphore(2)
        self.next_start = 0
        self.deadline = clock() + 3600

    def request(self, method, path, query=None, body=None, auth='valid', label=None):
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
                attempt = None
                if self.manifest is not None:
                    with LEDGER_LOCK:
                        m = self.manifest
                        wall = time.time()
                        if 'live_started_at' in m and wall - m['live_started_at'] >= 3600:
                            raise ValueError('Live deadline exhausted')
                        if m.get('http_requests', 0) >= 200 or (method == 'POST' and m.get('post_attempts', 0) >= 12):
                            raise ValueError('Task-wide budget exhausted')
                        records = m.setdefault('http_attempts', [])
                        if method == 'POST' and label and any(a.get('label') == label and a['method'] == 'POST' for a in records):
                            raise ValueError('Prior POST cannot be replayed')
                        m['http_requests'] = m.get('http_requests', 0) + 1
                        if method == 'POST':
                            m.setdefault('live_started_at', wall)
                            m['post_attempts'] = m.get('post_attempts', 0) + 1
                        attempt = {'number': m['http_requests'], 'method': method,
                                   'label': label or path, 'auth': auth, 'at': wall, 'state': 'reserved'}
                        records.append(attempt)
                        save_manifest(m)
            headers = {'Content-Type': 'application/json'}
            if auth != 'missing':
                headers['x-api-key'] = self.key if auth == 'valid' else 'invalid-offline-key'
            data = None if body is None else json.dumps(body, use_decimal=True).encode()
            target = self.url + path + ('?' + urlencode(query) if query else '')
            req = Request(target, data=data, headers=headers, method=method)
            try:
                remaining = self.deadline - self.clock()
                if self.manifest is not None and 'live_started_at' in self.manifest:
                    remaining = min(remaining, 3600 - (time.time() - self.manifest['live_started_at']))
                if remaining <= 0:
                    raise ValueError('HTTP deadline exhausted')
                response = build_opener(NoRedirect()).open(req, timeout=min(20, remaining))
            except HTTPError as error:
                response = error
            except Exception:
                if attempt is not None:
                    with LEDGER_LOCK:
                        attempt['state'] = 'ambiguous'
                        save_manifest(self.manifest)
                raise
            # No transport retry, including non-idempotent ambiguous timeouts.
            with response:
                raw = response.read(1024 * 1024)
                status = response.code
                backend = response.headers.get('X-Data-Backend')
            if attempt is not None:
                with LEDGER_LOCK:
                    attempt.update(state='response', status=status)
                    save_manifest(self.manifest)
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
    # A previous PASS is history, never evidence for another invocation.
    if name in m['scenarios']:
        m.setdefault('scenario_history', []).append({'name': name, 'result': m['scenarios'][name],
                                                    'binding': m.get('suite_binding'), 'at': time.time()})
    try:
        operation()
    except Exception as error:
        m['scenarios'][name] = 'BLOCKED: ' + safe_error(error)
        save_manifest(m)
        raise
    m['scenarios'][name] = 'PASS'
    save_manifest(m)


def pages(http, path, key, query, maximum=80, token_sink=None):
    items, seen = [], set()
    q = dict(query)
    for _ in range(maximum):
        body = expect(http, 'GET', path, 200, query=q)
        items.extend(body[key])
        token = body.get('next_token')
        if token_sink is not None and not token_sink:
            token_sink.append(token)
        if not token:
            return items
        if token in seen:
            raise AssertionError('Repeated pagination token')
        seen.add(token)
        q['next_token'] = token
    raise ValueError('Pagination budget exhausted')


def fixtures(s, m, run_id):
    if run_id != CONTINUATION:
        raise ValueError('Continuation mismatch')
    source = ROOT / 'plans/checkpoints/case-client-live-integration/host-case-live-20261019-1820/manifest.json'
    old = json.loads(source.read_text())
    if any(old.get(k) != m.get(k) for k in ('account', 'region', 'function', 'api_url')):
        raise ValueError('Fixture target mismatch')
    fs = old['fixtures']
    if (len(fs) != 4 or [f['status'] for f in fs] != ['active', 'active', 'inactive', 'blocked']
            or any(f['state'] != 'created' or f['source'] != 'synthetic' for f in fs)):
        raise ValueError('Missing verified fixture inventory')
    if m.get('fixtures') and m['fixtures'] != fs:
        raise ValueError('Fixture inventory changed')
    m['fixtures'] = fs
    m['fixture_source'] = str(source.relative_to(ROOT))
    m['fixture_run_id'] = old['run_id']
    m['fixture_case_ids'] = old['case_ids']
    save_manifest(m)
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


def fixture_inventory(s, m):
    """Read the complete existing synthetic partitions, never infer emptiness."""
    inventory = {f['client_id']: case_partition(s, f['client_id'])
                 for f in m['fixtures'] if f['status'] == 'active'}
    observed = {i for ids in inventory.values() for i in ids}
    if not set(m.get('fixture_case_ids', []) + m.get('case_ids', [])) <= observed:
        raise ValueError('Known fixture case missing')
    if m.get('fixture_inventory') and m['fixture_inventory'] != inventory:
        m.setdefault('fixture_inventory_history', []).append(m['fixture_inventory'])
    m['fixture_inventory'] = inventory
    save_manifest(m)
    return inventory


def write_matrix(s, http, m, run_id):
    fs = fixtures(s, m, run_id)
    prior_inventory = fixture_inventory(s, m)
    active, other, inactive, blocked = [f['client_id'] for f in fs]
    missing = m.setdefault('missing_client_id', str(uuid4()))
    save_manifest(m)
    path = lambda c: f'/clients/{c}/cases'
    # Validate all imported clients through their original ICO before any POST.
    for fixture in fs:
        values = pages(http, '/clients', 'clients', {'ico': fixture['ico'], 'limit': '1'})
        matches = [v for v in values if v['client_id'] == fixture['client_id']]
        assert len(matches) == 1 and matches[0]['status'] == fixture['status']
    inventory = [expect(http, 'GET', '/cases/' + case_id, 200) for case_id in m['fixture_case_ids']]
    assert all(c['client_id'] in (active, other) for c in inventory)
    metadata = {'run_id': run_id, 'nested': {'amount': Decimal('123456789.123456789012345678'),
                'values': [None, True, Decimal('0.1000000000000000001')]}}
    ledger_lock = threading.Lock()

    def post(label, client, caller=None):
        label = run_id + '-' + label
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
            attempts[label] = {'client_id': client, 'state': 'reserved'}
            save_manifest(m)
        try:
            value = expect(http, 'POST', '/cases', 201, body=body, label=label)
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
        original_name = fs[0]['name'].replace('Syntetický Žluťoučký', 'SYNTETICKY ZLUTOUCKY').replace('s.r.o.', 'společnost s ručením omezeným')
        q = {'name': original_name,
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
            stable = run_id + '-reject-' + label
            prior = m.setdefault('rejections', {}).get(stable)
            if prior is None:
                m['rejections'][stable] = 'reserved'
                save_manifest(m)
                expect(http, 'POST', '/cases', status, body={'client_id': client,
                    'metadata': {'run_id': run_id, 'label': label}}, label=stable)
                m['rejections'][stable] = status
                save_manifest(m)
            elif prior != status:
                raise ValueError('Ambiguous prior rejection POST')
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
            wanted |= {c['case_id'] for c in inventory if c['client_id'] == client}
            wanted |= set(prior_inventory[client])
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
    expected = []
    for client in (active, other):
        expected.extend(pages(http, path(client), 'cases', {'limit': '20'}))
    global_matrix(http, m, expected)


def global_matrix(http, m, expected, *, compact=False, client_token=None):
    def matrix():
        for auth in ('missing', 'wrong'):
            expect(http, 'GET', '/cases', 403, auth=auth)
        expect(http, 'GET', '/cases', 400, query={'next_token': 'bad!'})
        if not compact:
            for limit in ('0', '101', 'bad'):
                expect(http, 'GET', '/cases', 400, query={'limit': limit})
        tokens = []
        values = pages(http, '/cases', 'cases', {'limit': '1'}, maximum=150, token_sink=tokens)
        ids = [c['case_id'] for c in values]
        assert len(ids) == len(set(ids))
        fields = {'case_id', 'client_id', 'status', 'created_at', 'metadata'}
        assert all(set(c) == fields for c in values)
        fixture_clients = {f['client_id'] for f in m['fixtures'] if f['status'] == 'active'}
        scoped = {c['case_id']: c for c in values if c['client_id'] in fixture_clients}
        assert scoped == {c['case_id']: c for c in expected}
        assert {c['client_id'] for c in scoped.values()} == fixture_clients
        token = tokens[0]
        assert token
        active = next(f['client_id'] for f in m['fixtures'] if f['status'] == 'active')
        for route, query in [('/cases', {'limit': '2'}), (f'/clients/{active}/cases', {'limit': '1'})]:
            expect(http, 'GET', route, 400, query={**query, 'next_token': token})
        if client_token is None:
            client = expect(http, 'GET', f'/clients/{active}/cases', 200, query={'limit': '1'})
            client_token_value = client['next_token']
        else:
            client_token_value = client_token
        assert client_token_value
        expect(http, 'GET', '/cases', 400, query={'limit': '1', 'next_token': client_token_value})
        clients = expect(http, 'GET', '/clients', 200, query={'limit': '1'})
        assert clients['next_token']
        expect(http, 'GET', '/cases', 400, query={'limit': '1', 'next_token': clients['next_token']})
        m['global_traversal'] = {'limit': 1, 'terminal_token': None, 'unique': True,
                                 'fixture_case_ids': sorted(scoped), 'both_active_clients': True,
                                 'object_count': len(values), 'public_fields': True, 'metadata_match': True,
                                 'auth_missing_wrong': [403, 403], 'malformed_token': 400,
                                 'changed_limit': 400, 'cross_route_tokens': [400, 400, 400]}
    scenario(m, 'global-pagination-and-tokens', matrix)


def continue_read_only(s, http, m, config, deployment):
    """Finish a failed read phase, retaining exact prior runner/binding evidence.

    This explicit continuation never repeats the write matrix or treats a prior
    unbound PASS as current evidence. All remaining reads spend the same ledger.
    """
    binding = m.get('suite_binding', {})
    required = {'auth', 'validation-and-missing', 'clients-search-normalization-and-pagination',
                'create-detail-decimal-repeat', 'caller-id-ignored-cross-client',
                'concurrent-posts-and-immediate-get', 'unknown-inactive-blocked-no-write'}
    if (binding.get('code') != config['CodeSha256'] or binding.get('gateway') != deployment
            or binding.get('runner') != 'da0c7d51ffb209bd62d1ea8716b3501f7742b7ae484c6b59e3ddc2a6e7fe974d'
            or any(m.get('scenarios', {}).get(n) != 'PASS' for n in required)
            or m.get('pre_live_revision') != config.get('RevisionId')
            or not m.get('http_attempts')
            or any(a['state'] != 'response' for a in m['http_attempts'])):
        raise ValueError('Read-only continuation lacks bound prior evidence')
    m.setdefault('suite_runs', []).append({'binding': binding, 'scenarios': dict(m['scenarios']),
        'http_end': m['http_requests'], 'at': time.time(), 'result': 'BLOCKED fixture inventory incomplete'})
    m['continuation_evidence'] = {'binding': binding, 'scenarios': sorted(required),
                                 'http_end': m['http_requests'], 'unchanged_revision': config['RevisionId']}
    m['suite_binding'] = {'code': config['CodeSha256'], 'gateway': deployment,
        'runner': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    inventory = fixture_inventory(s, m)
    expected, client_tokens = [], []
    def clients():
        for client in inventory:
            path = f'/clients/{client}/cases'
            values = pages(http, path, 'cases', {'limit': '20'})
            assert {c['case_id'] for c in values} == set(inventory[client])
            assert len(values) == len(inventory[client])
            assert [c['created_at'] for c in values] == sorted([c['created_at'] for c in values], reverse=True)
            if not client_tokens:
                first = expect(http, 'GET', path, 200, query={'limit': '1'})
                assert first['cases'] == values[:1] and first['next_token']
                second = expect(http, 'GET', path, 200, query={'limit': '1', 'next_token': first['next_token']})
                assert second['cases'] == values[1:2]
                client_tokens.append((client, first['next_token']))
            else:
                client_tokens.append((client, None))
            expected.extend(values)
        client, token = client_tokens[0]
        other = client_tokens[1][0]
        for route, query in [(f'/clients/{other}/cases', {'limit': '1'}),
                             (f'/clients/{client}/cases', {'limit': '2'}),
                             (f'/clients/{client}/cases', {'limit': '1', 'status': 'open'})]:
            expect(http, 'GET', route, 400, query={**query, 'next_token': token})
        m['client_continuation'] = {'inventory_counts': {k: len(v) for k, v in inventory.items()},
                                    'newest_first': True, 'limit1_prefix': True, 'query_bound': True}
    scenario(m, 'case-pages-newest-first-query-bound', clients)
    global_matrix(http, m, expected, compact=True, client_token=client_tokens[0][1])
    m['live_matrix'] = 'PASS: cumulative bound original-operation evidence plus read-only continuation'
    save_manifest(m)


def run(args):
    s = session()
    identity(s)
    m = load_manifest()
    if args.allow_writes:
        require_writes(allow_writes=True, run_id=args.run_id)
    http = Transport(api_key(s), manifest=m)
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
    gateway = s.client('apigateway', config=CONFIG)
    stage = gateway.get_stage(restApiId=API, stageName='v1')
    if getattr(args, 'continue_read_only', False) is True:
        validate_ledger(m, args.run_id)
        continue_read_only(s, http, m, config, stage['deploymentId'])
        after = s.client('lambda', config=CONFIG).get_function_configuration(FunctionName=FUNCTION)
        if fingerprint(after) != fingerprint(config):
            raise ValueError('Concurrent revision change: stopped')
        m['http_post_config'] = binding_readback(after)
        m['http_post_revision'] = after['RevisionId']
        save_manifest(m)
        return
    if args.allow_writes:
        validate_ledger(m, args.run_id)
        if stage['deploymentId'] != m.get('gateway_deployment_id'):
            raise ValueError('Gateway deployment mismatch')
    m.setdefault('scenario_history', []).append({'scenarios': m.get('scenarios', {}),
        'binding': m.get('suite_binding'), 'at': time.time()})
    m['scenarios'] = {}
    m['suite_binding'] = {'code': config['CodeSha256'], 'gateway': stage.get('deploymentId'),
                          'runner': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
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
    after = s.client('lambda', config=CONFIG).get_function_configuration(FunctionName=FUNCTION)
    if fingerprint(after) != fingerprint(config):
        raise ValueError('Concurrent revision change: stopped')
    m['http_post_config'] = binding_readback(after)
    m['http_post_revision'] = after.get('RevisionId')
    save_manifest(m)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--allow-writes', action='store_true')
    parser.add_argument('--run-id', default='')
    parser.add_argument('--baseline', action='store_true')
    parser.add_argument('--continue-read-only', action='store_true')
    args = parser.parse_args()
    try:
        with exclusive_run():
            try:
                run(args)
            except Exception as error:
                m = load_manifest()
                m.setdefault('failure_history', []).append({'at': time.time(), 'action': 'http-integration',
                    'error': safe_error(error), 'http_requests': m.get('http_requests'),
                    'post_attempts': m.get('post_attempts')})
                m.update(status='BLOCKED', blocker=safe_error(error), blocked_action='http-integration')
                save_manifest(m)
                print(json.dumps({'result': 'BLOCKED', 'error': safe_error(error)}))
                return 1
        print(json.dumps({'result': 'PASS', 'mode': 'write-matrix' if args.allow_writes else 'read-only'}))
        return 0
    except Exception as error:
        print(json.dumps({'result': 'BLOCKED', 'error': safe_error(error)}))
        return 1


if __name__ == '__main__':
    sys.exit(main())
