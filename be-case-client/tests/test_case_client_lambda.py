"""Offline integration tests: real HTTP handler and real in-memory adapter."""
import base64
from datetime import datetime
import importlib
import json
import os
from pathlib import Path
import sys
import unittest
from uuid import UUID
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

ACTIVE = '11111111-1111-4111-8111-111111111111'
OTHER = '22222222-2222-4222-8222-222222222222'
INACTIVE = '33333333-3333-4333-8333-333333333333'
BLOCKED = '44444444-4444-4444-8444-444444444444'
EMPTY = '55555555-5555-4555-8555-555555555555'
MISSING = '99999999-9999-4999-8999-999999999999'


class CaseClientLambdaTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {
            'DATA_BACKEND': 'mock', 'ALLOW_EPHEMERAL_MOCK': 'true'
        }, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.module = importlib.import_module('case_client_handler')
        self.adapter = importlib.import_module('case_client_mock_repository')
        self.repository = self.adapter.MockCaseClientRepository()
        self.handler = self.module.create_handler(repository=self.repository)

    def invoke(self, method='GET', resource='/clients', body=None, query=None,
               params=None, raw=None, encoded=False, expected=200):
        response = self.handler({
            'httpMethod': method, 'resource': resource, 'path': resource,
            'pathParameters': params, 'queryStringParameters': query,
            'body': raw if raw is not None else (
                None if body is None else json.dumps(body)),
            'isBase64Encoded': encoded,
        }, None)
        self.assertEqual(response['statusCode'], expected, response)
        self.assertEqual(response['headers']['X-Data-Backend'], 'mock')
        self.assertEqual(response['headers']['Content-Type'], 'application/json')
        self.assertIsInstance(response['body'], str)
        data = json.loads(response['body'])
        if expected >= 400:
            self.assertEqual(set(data), {'error'})
            self.assertIsInstance(data['error'], str)
        return data

    def post(self, case_id='offline-case', client_id=ACTIVE, expected=201, **extra):
        return self.invoke('POST', '/cases', body=dict(
            case_id=case_id, client_id=client_id, **extra), expected=expected)

    def cases(self, client=ACTIVE, query=None, expected=200):
        return self.invoke(resource='/clients/{client_id}/cases',
                           params={'client_id': client}, query=query, expected=expected)

    def test_clients_have_public_shape_and_mock_marker(self):
        data = self.invoke()
        self.assertGreaterEqual(len(data['clients']), 5)
        self.assertIsNone(data['next_token'])
        allowed = {'client_id', 'ico', 'dic', 'name', 'legal_form', 'address',
                   'status', 'contacts', 'signatories', 'kyc', 'source'}
        nested = {'contacts': {'name', 'role', 'email', 'phone', 'preferred_channel'},
                  'signatories': {'name', 'function', 'authorized'},
                  'kyc': {'status', 'checked_at'}}
        for client in data['clients']:
            self.assertLessEqual(set(client), allowed)
            self.assertLessEqual({'client_id', 'ico', 'name', 'status'}, set(client))
            self.assertEqual(str(UUID(client['client_id'])), client['client_id'])
            self.assertRegex(client['ico'], r'^[0-9]{8}$')
            checksum = sum(int(digit) * weight for digit, weight in zip(client['ico'][:7], range(8, 1, -1)))
            self.assertEqual(int(client['ico'][-1]), (11 - checksum % 11) % 10)
            self.assertEqual(client['source'], 'synthetic')
            for key, fields in nested.items():
                items = client.get(key, [] if key != 'kyc' else {})
                for item in items if isinstance(items, list) else [items]:
                    self.assertLessEqual(set(item), fields)

    def test_repeat_preserves_original_case_and_new_repository_resets(self):
        first = self.post(metadata={'note': 'první'})
        repeat = self.post(expected=200, metadata={'note': 'jiné'})
        self.assertEqual(first, repeat)
        self.assertEqual(first['status'], 'open')
        self.assertTrue(first['created_at'].endswith('Z'))
        self.assertEqual(self.invoke(resource='/cases/{case_id}',
                         params={'case_id': 'offline-case'}), first)
        self.handler = self.module.create_handler(self.adapter.MockCaseClientRepository())
        self.invoke(resource='/cases/{case_id}',
                    params={'case_id': 'offline-case'}, expected=404)

    def test_business_errors_and_existing_inactive_precedence(self):
        self.post()
        for client in (OTHER, MISSING):
            self.post(client_id=client, expected=409)
        for client in (INACTIVE, BLOCKED):
            self.post('new-' + client, client, expected=409)
        self.post('missing-client', MISSING, expected=404)
        original = self.invoke(resource='/cases/{case_id}', params={'case_id': 'fixture-inactive'})
        self.assertEqual(self.post('fixture-inactive', INACTIVE, expected=200,
                                  metadata={'changed': True}), original)
        self.assertEqual(self.cases(EMPTY)['cases'], [])
        self.cases(MISSING, expected=404)
        self.invoke(resource='/cases/{case_id}', params={'case_id': 'absent'}, expected=404)

    def test_filters_normalization_and_and_semantics(self):
        for name in ('ŽLUŤOUČKÁ', 'zlutoucka s.r.o.', 'Žluťoučká společnost s ručením omezeným'):
            data = self.invoke(query={'name': name, 'status': 'active', 'ico': '00000019'})
            self.assertEqual([c['client_id'] for c in data['clients']], [ACTIVE])
        self.assertEqual(self.invoke(query={'name': 'žluťoučká', 'status': 'inactive'})['clients'], [])
        for name in ('JASAN', 'jasan a.s.', 'Jasan akciová společnost'):
            self.assertEqual([c['client_id'] for c in self.invoke(query={'name': name})['clients']], [OTHER])
        # Legal forms must not remove ordinary word substrings (e.g. 'as' in Jasan).
        self.assertEqual(len(self.invoke(query={'name': 'jasan'})['clients']), 1)

    def test_pagination_query_binding_and_cross_repository(self):
        first = self.invoke(query={'limit': '1'})
        token = first['next_token']
        self.assertIsInstance(token, str)
        seen = [first['clients'][0]['client_id']]
        self.handler = self.module.create_handler(self.adapter.MockCaseClientRepository())
        while token:
            page = self.invoke(query={'limit': '1', 'next_token': token})
            seen.extend(c['client_id'] for c in page['clients'])
            token = page['next_token']
        self.assertEqual(seen, sorted(set(seen)))
        self.assertGreaterEqual(len(seen), 5)
        token = first['next_token']
        for query in ({'limit': '2'}, {'limit': '1', 'status': 'active'},
                      {'limit': '1', 'name': 'Jasan'}):
            self.invoke(query=dict(query, next_token=token), expected=400)
        self.cases(query={'limit': '1', 'next_token': token}, expected=400)
        deep = base64.urlsafe_b64encode(('[' * 1100 + ']' * 1100).encode()).decode().rstrip('=')
        for bad in ('!', 'e30', 'x' * 4097, '', '====', 'é', deep):
            self.invoke(query={'next_token': bad}, expected=400)
        payload = json.loads(base64.urlsafe_b64decode(first['next_token'] + '==='))
        for changes in ({'last': 'absent'}, {'v': True}, {'extra': 1}):
            altered = dict(payload, **changes)
            bad = base64.urlsafe_b64encode(json.dumps(altered).encode()).decode().rstrip('=')
            self.invoke(query={'limit': '1', 'next_token': bad}, expected=400)

    def test_case_sort_pagination_and_client_binding(self):
        all_cases = self.cases()['cases']
        self.assertGreaterEqual(len(all_cases), 3)
        self.assertEqual(all_cases, sorted(all_cases, key=lambda c: (-datetime.fromisoformat(
            c['created_at'].replace('Z', '+00:00')).timestamp(), c['case_id'])))
        page = self.cases(query={'status': 'open', 'limit': '1'})
        token = page['next_token']
        self.cases(OTHER, {'status': 'open', 'limit': '1', 'next_token': token}, expected=400)
        found = page['cases'][:]
        while token:
            page = self.cases(query={'status': 'open', 'limit': '1', 'next_token': token})
            found += page['cases']
            token = page['next_token']
        self.assertEqual(found, all_cases)

    def test_query_validation_boundaries(self):
        for query in ({'ico': '123'}, {'ico': '１２３４５６７８'}, {'name': 'x'},
                      {'name': 'x' * 256}, {'name': 's.r.o.'}, {'name': '  '},
                      {'status': 'closed'}, {'limit': '0'}, {'limit': '101'},
                      {'limit': '1.0'}, {'limit': '-1'}, {'limit': True}, {'name': 12}):
            with self.subTest(query=query):
                self.invoke(query=query, expected=400)
        for size in (2, 255):
            self.invoke(query={'name': 'x' * size})
        for limit in ('1', '50', '100'):
            self.invoke(query={'limit': limit})
        for status in ('active', 'inactive', 'blocked'):
            self.invoke(query={'status': status})
        self.cases(query={'status': 'closed'}, expected=400)

    def test_request_validation_and_base64(self):
        for body in ([], None, {}, {'case_id': 'a'}, {'case_id': 'a', 'client_id': 'wrong'},
                     {'case_id': 'a/b', 'client_id': ACTIVE}, {'case_id': '', 'client_id': ACTIVE},
                     {'case_id': 'x' * 129, 'client_id': ACTIVE},
                     {'case_id': True, 'client_id': ACTIVE},
                     {'case_id': 'a', 'client_id': ACTIVE, 'metadata': []}):
            self.invoke('POST', '/cases', body=body, expected=400)
        for raw in ('', '{', 'null', '{"case_id":"a","client_id":"' + ACTIVE + '","metadata":{"v":NaN}}',
                    '{"case_id":"a","client_id":"' + ACTIVE + '","metadata":{"v":Infinity}}'):
            self.invoke('POST', '/cases', raw=raw, expected=400)
        self.post('x' * 128)
        self.post('a')
        raw = base64.b64encode(json.dumps({'case_id': 'base64', 'client_id': ACTIVE}).encode()).decode()
        self.invoke('POST', '/cases', raw=raw, encoded=True, expected=201)
        self.invoke('POST', '/cases', raw='!', encoded=True, expected=400)
        for bad in ('bad', '', None):
            self.cases(bad, expected=400)
        self.invoke(resource='/cases/{case_id}', params={'case_id': 'bad/id'}, expected=400)

    def test_metadata_utf8_limit(self):
        # {"x":""} is 8 bytes; Czech character is 2 bytes in UTF-8.
        metadata = {'x': 'á' * ((16384 - 8) // 2)}
        self.post('exact-limit', metadata=metadata)
        metadata['x'] += 'a'
        self.post('over-limit', metadata=metadata, expected=400)

    def test_fail_closed_configuration_and_operational_errors(self):
        for key, value in (('DATA_BACKEND', None), ('DATA_BACKEND', 'db'),
                           ('ALLOW_EPHEMERAL_MOCK', None), ('ALLOW_EPHEMERAL_MOCK', 'TRUE')):
            with patch.dict(os.environ):
                if value is None:
                    os.environ.pop(key)
                else:
                    os.environ[key] = value
                with self.assertRaises(RuntimeError):
                    self.module.create_handler(self.repository)
                response = self.module.lambda_handler({'httpMethod': 'GET', 'path': '/clients'}, None)
                self.assertEqual(response['statusCode'], 500)
                self.assertNotIn('X-Data-Backend', response['headers'])
        with patch.object(self.repository, 'list_clients', side_effect=RuntimeError('secret')):
            error = self.invoke(expected=500)
            self.assertNotIn('secret', error['error'])

    def test_path_routing_and_methods(self):
        response = self.handler({'httpMethod': 'GET', 'path': '/cases/fixture-old'}, None)
        self.assertEqual(response['statusCode'], 200)
        self.invoke('DELETE', '/clients', expected=405)
        self.invoke(resource='/unknown', expected=404)

    def test_no_network_or_aws_dependencies(self):
        import ast
        import socket
        with patch.object(socket, 'socket', side_effect=AssertionError('network forbidden')), \
                patch.object(socket, 'getaddrinfo', side_effect=AssertionError('DNS forbidden')):
            importlib.reload(self.adapter)
            importlib.reload(self.module)
            self.handler = self.module.create_handler(self.adapter.MockCaseClientRepository())
            self.invoke()
            self.post('offline-network')
        for path in (Path(__file__).resolve().parents[1] / 'src').glob('*.py'):
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                names = [n.name for n in node.names] if isinstance(node, ast.Import) else (
                    [node.module or ''] if isinstance(node, ast.ImportFrom) else [])
                for name in names:
                    self.assertNotIn(name.split('.')[0],
                                     {'boto3', 'botocore', 'requests', 'urllib', 'http', 'socket'})

    def test_deep_copy_and_atomic_create(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        metadata = {'nested': {'items': [1]}}
        first, created = self.repository.create_case('copy', ACTIVE, metadata)
        self.assertTrue(created)
        metadata['nested']['items'].append(2)
        first['metadata']['nested']['items'].append(3)
        self.assertEqual(self.repository.get_case('copy')['metadata']['nested']['items'], [1])
        clients = self.repository.list_clients({}, 50)['clients']
        clients[0]['contacts'][0]['email'] = 'changed@demo.example'
        self.assertEqual(self.repository.list_clients({}, 50)['clients'][0]['contacts'][0]['email'],
                         'kontakt@zlutoucka.example')
        self.assertEqual(self.adapter.MockCaseClientRepository().list_clients({}, 50)['clients'][0]['contacts'][0]['email'],
                         'kontakt@zlutoucka.example')
        for case_id, owners, statuses in (
                ('concurrent-same', [ACTIVE, ACTIVE], [200, 201]),
                ('concurrent-different', [ACTIVE, OTHER], [201, 409])):
            barrier = Barrier(2)
            def call(owner):
                barrier.wait()
                return self.handler({'httpMethod': 'POST', 'path': '/cases',
                                     'body': json.dumps({'case_id': case_id, 'client_id': owner})}, None)['statusCode']
            with ThreadPoolExecutor(max_workers=2) as pool:
                self.assertEqual(sorted(pool.map(call, owners)), statuses)

    def test_packaged_events_and_case_public_shape(self):
        directory = Path(__file__).resolve().parents[1] / 'events'
        for name in ('list-clients', 'create-case', 'get-case', 'list-client-cases'):
            response = self.handler(json.loads((directory / (name + '.json')).read_text()), None)
            self.assertEqual(response['statusCode'], 201 if name == 'create-case' else 200)
            self.assertEqual(response['headers']['X-Data-Backend'], 'mock')
        case = self.invoke(resource='/cases/{case_id}', params={'case_id': 'fixture-old'})
        self.assertEqual(set(case), {'case_id', 'client_id', 'status', 'created_at', 'metadata'})
        # Cases and their nested metadata returned by the adapter cannot mutate fixtures.
        case = self.repository.get_case('fixture-old')
        case['metadata']['demo'] = False
        self.assertTrue(self.repository.get_case('fixture-old')['metadata']['demo'])


if __name__ == '__main__':
    unittest.main()
