"""Offline real handler/SDK integration; all requests must be consumed by Stubber."""
import json
import os
from decimal import Decimal
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import base64
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import boto3
from boto3.dynamodb.types import TypeSerializer
from botocore.stub import Stubber
from botocore.exceptions import ReadTimeoutError, EndpointConnectionError
import case_client_handler
from case_client_repository import InvalidRequest, Conflict, NotFound

ACTIVE = '11111111-1111-4111-8111-111111111111'
ENV = {
    'DATA_BACKEND': 'dynamodb', 'CLIENTS_TABLE_NAME': 'wonderfulkb-uw-clients',
    'CASES_TABLE_NAME': 'wonderfulkb-uw-cases', 'CLIENTS_ICO_INDEX_NAME': 'ico-index',
    'CASES_CLIENT_CREATED_INDEX_NAME': 'client-created-index',
    'AWS_REGION': 'eu-central-1', 'AWS_DEFAULT_REGION': 'eu-central-1',
    'AWS_EC2_METADATA_DISABLED': 'true', 'AWS_CONFIG_FILE': os.devnull,
    'AWS_SHARED_CREDENTIALS_FILE': os.devnull,
    'AWS_ACCESS_KEY_ID': 'offline', 'AWS_SECRET_ACCESS_KEY': 'offline',
}


class DynamoDBHandlerTests(unittest.TestCase):
    def setUp(self):
        for p in (patch.dict(os.environ, ENV, clear=True),
                  patch('socket.socket', side_effect=AssertionError('network forbidden')),
                  patch('socket.getaddrinfo', side_effect=AssertionError('DNS forbidden'))):
            p.start()
            self.addCleanup(p.stop)

    def test_factory_strong_get_preserves_decimal_and_backend(self):
        case = {'case_id': 'offline-db', 'client_id': ACTIVE, 'status': 'open',
                'created_at': '2026-10-19T12:00:00.000000Z',
                'metadata': {'nested': [None, True, Decimal('0.1234567890123456789')]}}
        with patch.dict(os.environ, ENV, clear=True), \
                patch('socket.socket', side_effect=AssertionError('network forbidden')), \
                patch('socket.getaddrinfo', side_effect=AssertionError('DNS forbidden')):
            sdk = boto3.client('dynamodb', region_name='eu-central-1',
                               aws_access_key_id='offline', aws_secret_access_key='offline')
            self.addCleanup(sdk.close)
            with Stubber(sdk) as stub, patch('boto3.client', return_value=sdk), \
                    patch.object(case_client_handler, '_cached_handler', None):
                stub.add_response('get_item', {
                    'Item': TypeSerializer().serialize(dict(case, internal='hidden'))['M']
                }, {'TableName': ENV['CASES_TABLE_NAME'],
                    'Key': {'case_id': {'S': 'offline-db'}}, 'ConsistentRead': True})
                result = case_client_handler.lambda_handler({
                    'httpMethod': 'GET', 'resource': '/cases/{case_id}',
                    'pathParameters': {'case_id': 'offline-db'},
                }, None)
                self.assertEqual(result['statusCode'], 200, result)
                self.assertEqual(result['headers']['X-Data-Backend'], 'dynamodb')
                self.assertEqual(json.loads(result['body'], parse_float=Decimal), case)
                stub.assert_no_pending_responses()

    def test_configuration_fail_closed_even_when_injected(self):
        for key in ('CLIENTS_TABLE_NAME', 'CASES_TABLE_NAME', 'CLIENTS_ICO_INDEX_NAME',
                    'CASES_CLIENT_CREATED_INDEX_NAME', 'AWS_REGION'):
            for value in ('', ' invalid ', 'x' * 256):
                env = dict(ENV, **{key: value})
                if key == 'AWS_REGION':
                    env.pop('AWS_DEFAULT_REGION')
                with self.subTest(key=key, value=value), patch.dict(os.environ, env, clear=True):
                    with self.assertRaises(RuntimeError):
                        case_client_handler.create_handler(object())
                    response = case_client_handler.lambda_handler({}, None)
                    self.assertEqual(response['statusCode'], 500)
                    self.assertNotIn('X-Data-Backend', response['headers'])
        with patch.dict(os.environ, dict(ENV, CASES_TABLE_NAME=ENV['CLIENTS_TABLE_NAME']), clear=True):
            with self.assertRaises(RuntimeError):
                case_client_handler.create_handler(object())
        with patch.dict(os.environ, ENV, clear=True):
            os.environ.pop('AWS_REGION')
            self.assertEqual(case_client_handler._configured()[1]['region'], 'eu-central-1')

    def test_warm_cache_reconfigures_and_never_serves_old_mock_on_sdk_failure(self):
        with patch.dict(os.environ, {'DATA_BACKEND': 'mock', 'ALLOW_EPHEMERAL_MOCK': 'true'}, clear=True), \
                patch.object(case_client_handler, '_cached_handler', None), \
                patch.object(case_client_handler, '_cached_configuration', None):
            event = {'httpMethod': 'GET', 'resource': '/clients'}
            self.assertEqual(case_client_handler.lambda_handler(event, None)['headers']['X-Data-Backend'], 'mock')
            with patch.dict(os.environ, ENV, clear=True), \
                    patch('boto3.client', side_effect=RuntimeError('secret')) as factory:
                response = case_client_handler.lambda_handler(event, None)
                self.assertEqual(response['statusCode'], 500)
                self.assertNotIn('X-Data-Backend', response['headers'])
                config = factory.call_args.kwargs['config']
                self.assertEqual(config.connect_timeout, 1)
                self.assertEqual(config.read_timeout, 2)
                self.assertEqual(config.retries['total_max_attempts'], 1)


def wire(item):
    return TypeSerializer().serialize(item)['M']


def client(client_id=ACTIVE, **changes):
    return dict({'client_id': client_id, 'ico': '00000019',
                 'name': 'Žluťoučká s.r.o.', 'status': 'active'}, **changes)


def case(case_id='offline-db', **changes):
    return dict({'case_id': case_id, 'client_id': ACTIVE, 'status': 'open',
                 'created_at': '2026-10-19T12:00:00.000000Z', 'metadata': {}}, **changes)


class DynamoDBRepositoryTests(unittest.TestCase):
    def setUp(self):
        for p in (patch.dict(os.environ, ENV, clear=True),
                  patch('socket.socket', side_effect=AssertionError('network forbidden')),
                  patch('socket.getaddrinfo', side_effect=AssertionError('DNS forbidden'))):
            p.start()
            self.addCleanup(p.stop)
        self.sdk = boto3.client('dynamodb', region_name=ENV['AWS_REGION'],
                                aws_access_key_id='offline', aws_secret_access_key='offline')
        self.addCleanup(self.sdk.close)
        self.stub = Stubber(self.sdk)
        self.stub.activate()
        self.addCleanup(self.stub.deactivate)
        self.repo = self.repository()

    def tearDown(self):
        self.stub.assert_no_pending_responses()

    def repository(self, **changes):
        from case_client_dynamodb_repository import DynamoDBCaseClientRepository
        options = dict(clients_table=ENV['CLIENTS_TABLE_NAME'], cases_table=ENV['CASES_TABLE_NAME'],
                       clients_ico_index='ico-index', cases_client_created_index='client-created-index',
                       region='eu-central-1')
        options.update(changes)
        return DynamoDBCaseClientRepository(self.sdk, **options)

    def get(self, kind, value, item):
        key = 'client_id' if kind == 'clients' else 'case_id'
        params = {'TableName': ENV[kind.upper() + '_TABLE_NAME'],
                  'Key': {key: {'S': value}}, 'ConsistentRead': True}
        self.stub.add_response('get_item', {} if item is None else {'Item': wire(item)}, params)

    def scan(self, items, limit=2, start=None, last=None):
        params = {'TableName': ENV['CLIENTS_TABLE_NAME'], 'Limit': min(limit, 25)}
        if start:
            params['ExclusiveStartKey'] = start
        response = {'Items': [wire(i) for i in items]}
        if last:
            response['LastEvaluatedKey'] = last
        self.stub.add_response('scan', response, params)

    def transaction(self, metadata=None, error=None, reasons=None):
        new = case(metadata={} if metadata is None else metadata)
        params = {'TransactItems': [
            {'ConditionCheck': {'TableName': ENV['CLIENTS_TABLE_NAME'],
                'Key': {'client_id': {'S': ACTIVE}},
                'ConditionExpression': 'attribute_exists(#id) AND #status = :active',
                'ExpressionAttributeNames': {'#id': 'client_id', '#status': 'status'},
                'ExpressionAttributeValues': {':active': {'S': 'active'}}}},
            {'Put': {'TableName': ENV['CASES_TABLE_NAME'], 'Item': wire(new),
                'ConditionExpression': 'attribute_not_exists(#id)',
                'ExpressionAttributeNames': {'#id': 'case_id'}}}]}
        if error:
            self.stub.add_client_error('transact_write_items', service_error_code=error,
                service_message='DO NOT EXPOSE secret metadata', expected_params=params,
                modeled_fields={} if reasons is None else {'CancellationReasons': reasons})
        else:
            self.stub.add_response('transact_write_items', {}, params)

    def create(self, metadata=None):
        with patch('case_client_dynamodb_repository.datetime') as clock:
            clock.now.return_value = datetime(2026, 10, 19, 12, tzinfo=timezone.utc)
            return self.repo.create_case('offline-db', ACTIVE, {} if metadata is None else metadata)

    def invoke(self, resource='/clients', method='GET', query=None, body=None, params=None, expected=200):
        result = case_client_handler.create_handler(self.repo)({
            'httpMethod': method, 'resource': resource, 'pathParameters': params,
            'queryStringParameters': query, 'body': body}, None)
        self.assertEqual(result['statusCode'], expected, result)
        self.assertEqual(result['headers']['X-Data-Backend'], 'dynamodb')
        data = json.loads(result['body'], parse_float=Decimal)
        if expected >= 400:
            self.assertEqual(set(data), {'error'})
            self.assertNotIn('secret', result['body'])
        return data

    def test_handler_scan_and_allowlisted_nested_client(self):
        stored = client(internal='hidden', contacts=[{'name': 'Test', 'internal': 'hidden'}],
                        kyc={'status': 'ok', 'checked_at': '2026-10-19', 'private': True})
        self.scan([stored], limit=50)
        result = self.invoke()['clients'][0]
        self.assertNotIn('internal', result)
        self.assertEqual(result['contacts'], [{'name': 'Test'}])
        self.assertEqual(result['kyc'], {'status': 'ok', 'checked_at': '2026-10-19'})
        self.assertNotIn('source', result)

    def test_ico_query_and_normalized_and_filters(self):
        self.stub.add_response('query', {'Items': [wire(client()), wire(client(status='inactive'))]}, {
            'TableName': ENV['CLIENTS_TABLE_NAME'], 'IndexName': 'ico-index',
            'KeyConditionExpression': '#ico = :ico', 'ExpressionAttributeNames': {'#ico': 'ico'},
            'ExpressionAttributeValues': {':ico': {'S': '00000019'}}, 'Limit': 25})
        data = self.invoke(query={'ico': '00000019', 'name': 'ŽLUŤOUČKÁ s.r.o.', 'status': 'active'})
        self.assertEqual(data['clients'], [client()])

    def test_name_filter_uses_same_single_normalization_as_mock(self):
        # Removing a legal form can join fragments into another legal form.
        # The handler owns filter normalization, as in the mock repository.
        self.scan([client()], limit=50)
        self.assertEqual(self.invoke(query={'name': 'Žluťoučká a. a.s. s.'})['clients'], [])

    def test_scan_empty_filtered_pages_and_cross_instance_overflow_resume(self):
        key = {'client_id': {'S': 'cursor'}}
        key2 = {'client_id': {'S': 'cursor2'}}
        self.scan([], last=key)
        self.scan([client(status='inactive')], start=key, last=key2)
        a, b, c = [client(client_id=v) for v in (
            ACTIVE, '22222222-2222-4222-8222-222222222222', '33333333-3333-4333-8333-333333333333')]
        # Fake SDK can return an overfull final page; only emitted cursor may be used.
        self.scan([a, b, c], start=key2)
        first = self.repo.list_clients({'status': 'active'}, 2)
        self.assertEqual(first['clients'], [a, b])
        self.scan([c], start={'client_id': {'S': b['client_id']}})
        second = self.repository().list_clients({'status': 'active'}, 2, first['next_token'])
        self.assertEqual(second, {'clients': [c], 'next_token': None})

    def test_bounded_empty_scan_and_deadline(self):
        for n in range(8):
            self.scan([], last={'client_id': {'S': str(n)}},
                      start=None if n == 0 else {'client_id': {'S': str(n - 1)}})
        page = self.repo.list_clients({}, 2)
        self.assertEqual(page['clients'], [])
        self.assertTrue(page['next_token'])
        self.scan([], last={'client_id': {'S': 'deadline'}})
        times = iter([0, 0, 5])
        page = self.repository(clock=lambda: next(times)).list_clients({}, 2)
        self.assertTrue(page['next_token'])

    def test_tokens_validate_before_any_sdk_call(self):
        self.scan([], last={'client_id': {'S': 'cursor'}})
        times = iter([0, 0, 5])
        page = self.repository(clock=lambda: next(times)).list_clients({}, 2)
        token = page['next_token']
        deep = base64.urlsafe_b64encode(('[' * 1100 + ']' * 1100).encode()).decode().rstrip('=')
        bad_tokens = ['!', '', 'e30', 'x' * 4097, deep, token + '=',
                      base64.urlsafe_b64encode(b'{"v":1}').decode().rstrip('=')]
        payload = json.loads(base64.urlsafe_b64decode(token + '==='))
        for changes in ({'v': True}, {'extra': 1}, {'last': {'client_id': {'N': '3'}}},
                        {'last': {'client_id': {'S': ''}}}, {'last': []}):
            bad_tokens.append(base64.urlsafe_b64encode(json.dumps(dict(payload, **changes)).encode()).decode().rstrip('='))
        for bad in bad_tokens:
            with self.subTest(bad=bad[:20]), self.assertRaises(InvalidRequest):
                self.repo.list_clients({}, 2, bad)
        for changes in ({'region': 'us-east-1'}, {'clients_table': 'other-clients'},
                        {'cases_table': 'other-cases'}, {'clients_ico_index': 'other-index'},
                        {'cases_client_created_index': 'other-index'}):
            with self.assertRaises(InvalidRequest):
                self.repository(**changes).list_clients({}, 2, token)
        for filters, limit in (({'status': 'active'}, 2), ({}, 1)):
            with self.assertRaises(InvalidRequest):
                self.repo.list_clients(filters, limit, token)
        with self.assertRaises(InvalidRequest):
            self.repo.list_client_cases(ACTIVE, {}, 2, token)
        from case_client_mock_repository import MockCaseClientRepository
        mock_token = MockCaseClientRepository().list_clients({}, 2)['next_token']
        with self.assertRaises(InvalidRequest):
            self.repo.list_clients({}, 2, mock_token)

    def test_case_list_exact_query_and_resume_tied_timestamps(self):
        a, b = case('a'), case('b')
        self.get('clients', ACTIVE, client())
        query = {'TableName': ENV['CASES_TABLE_NAME'], 'IndexName': 'client-created-index',
                 'KeyConditionExpression': '#client = :client',
                 'ExpressionAttributeNames': {'#client': 'client_id'},
                 'ExpressionAttributeValues': {':client': {'S': ACTIVE}},
                 'ScanIndexForward': False, 'Limit': 1}
        self.stub.add_response('query', {'Items': [wire(a), wire(b)]}, query)
        first = self.invoke('/clients/{client_id}/cases', params={'client_id': ACTIVE},
                            query={'limit': '1', 'status': 'open'})
        self.get('clients', ACTIVE, client())
        key = {k: {'S': a[k]} for k in ('case_id', 'client_id', 'created_at')}
        self.stub.add_response('query', {'Items': [wire(b)]}, dict(query, ExclusiveStartKey=key))
        second = self.repository().list_client_cases(ACTIVE, {'status': 'open'}, 1, first['next_token'])
        self.assertEqual(first['cases'] + second['cases'], [a, b])
        self.assertIsNone(second['next_token'])
        with self.assertRaises(InvalidRequest):
            self.repo.list_client_cases('22222222-2222-4222-8222-222222222222',
                                       {'status': 'open'}, 1, first['next_token'])

    def test_ico_cursor_contains_both_keys_and_survives_new_instance(self):
        query = {'TableName': ENV['CLIENTS_TABLE_NAME'], 'IndexName': 'ico-index',
                 'KeyConditionExpression': '#ico = :ico',
                 'ExpressionAttributeNames': {'#ico': 'ico'},
                 'ExpressionAttributeValues': {':ico': {'S': '00000019'}}, 'Limit': 1}
        a, b = client(), client(client_id='22222222-2222-4222-8222-222222222222')
        self.stub.add_response('query', {'Items': [wire(a), wire(b)]}, query)
        first = self.repo.list_clients({'ico': '00000019'}, 1)
        key = {k: {'S': a[k]} for k in ('client_id', 'ico')}
        self.stub.add_response('query', {'Items': [wire(b)]}, dict(query, ExclusiveStartKey=key))
        second = self.repository().list_clients({'ico': '00000019'}, 1, first['next_token'])
        self.assertEqual(first['clients'] + second['clients'], [a, b])
        self.assertIsNone(second['next_token'])
        with self.assertRaises(InvalidRequest):
            self.repo.list_clients({'ico': '00000000'}, 1, first['next_token'])

    def test_full_page_lek_resumes_to_empty_end_without_losing_results(self):
        key = {'client_id': {'S': ACTIVE}}
        self.scan([client()], limit=1, last=key)
        first = self.repo.list_clients({}, 1)
        self.scan([], limit=1, start=key)
        self.assertEqual(self.repository().list_clients({}, 1, first['next_token']),
                         {'clients': [], 'next_token': None})

    def test_maximum_evaluated_items_and_shorter_lambda_budget(self):
        for n in range(8):
            self.scan([], limit=100, last={'client_id': {'S': str(n)}},
                      start=None if n == 0 else {'client_id': {'S': str(n - 1)}})
        self.assertTrue(self.repo.list_clients({}, 100)['next_token'])
        for remaining in (0, 1, 2.9):
            with self.assertRaises(RuntimeError):
                self.repository(time_remaining=lambda: remaining).list_clients({}, 2)
        self.scan([], last={'client_id': {'S': 'short'}})
        times = iter([0, 0, 1])
        result = self.repository(time_remaining=lambda: 3.5, clock=lambda: next(times)).list_clients({}, 2)
        self.assertTrue(result['next_token'])

    def test_missing_case_client_and_empty_cases(self):
        self.get('cases', 'absent', None)
        self.invoke('/cases/{case_id}', params={'case_id': 'absent'}, expected=404)
        self.get('clients', ACTIVE, None)
        self.invoke('/clients/{client_id}/cases', params={'client_id': ACTIVE}, expected=404)
        self.get('clients', ACTIVE, client())
        self.stub.add_response('query', {'Items': []}, {
            'TableName': ENV['CASES_TABLE_NAME'], 'IndexName': 'client-created-index',
            'KeyConditionExpression': '#client = :client',
            'ExpressionAttributeNames': {'#client': 'client_id'},
            'ExpressionAttributeValues': {':client': {'S': ACTIVE}},
            'ScanIndexForward': False, 'Limit': 25})
        self.assertEqual(self.invoke('/clients/{client_id}/cases', params={'client_id': ACTIVE})['cases'], [])

    def test_create_then_new_instance_idempotence_and_owner_conflict(self):
        metadata = {'nested': [None, True, 17, Decimal('0.1234567890123456789')]}
        self.get('cases', 'offline-db', None)
        self.get('clients', ACTIVE, client())
        self.transaction(metadata)
        created, is_new = self.create(metadata)
        self.assertTrue(is_new)
        self.assertEqual(created, case(metadata=metadata))
        self.get('cases', 'offline-db', created)
        self.repo = self.repository()
        self.assertEqual(self.create({'changed': True}), (created, False))
        self.get('cases', 'offline-db', case(client_id='22222222-2222-4222-8222-222222222222'))
        with self.assertRaises(Conflict):
            self.create()

    def test_post_handler_decimal_201_then_200_without_client_read(self):
        self.get('cases', 'offline-db', None)
        self.get('clients', ACTIVE, client())
        self.transaction({'n': Decimal('0.1234567890123456789')})
        raw = '{"case_id":"offline-db","client_id":"' + ACTIVE + '","metadata":{"n":0.1234567890123456789}}'
        with patch('case_client_dynamodb_repository.datetime') as clock:
            clock.now.return_value = datetime(2026, 10, 19, 12, tzinfo=timezone.utc)
            first = self.invoke('/cases', 'POST', body=raw, expected=201)
        self.get('cases', 'offline-db', first)
        self.repo = self.repository()
        self.assertEqual(self.invoke('/cases', 'POST', body=raw), first)

    def test_new_client_business_errors_and_existing_precedence(self):
        for status, expected in ((None, NotFound), ('inactive', Conflict), ('blocked', Conflict)):
            self.get('cases', 'offline-db', None)
            self.get('clients', ACTIVE, None if status is None else client(status=status))
            with self.assertRaises(expected):
                self.create()
            self.get('cases', 'offline-db', case())
            self.assertEqual(self.create(), (case(), False))

    def test_condition_race_recovery(self):
        for winner, current_client, expected in (
                (case(metadata={'winner': True}), None, None),
                (case(client_id='22222222-2222-4222-8222-222222222222'), None, Conflict),
                (None, None, NotFound), (None, client(status='blocked'), Conflict),
                (None, client(status='inactive'), Conflict), (None, client(), RuntimeError)):
            self.get('cases', 'offline-db', None)
            self.get('clients', ACTIVE, client())
            self.transaction(error='TransactionCanceledException', reasons=[
                {'Code': 'None' if winner is not None else 'ConditionalCheckFailed'},
                {'Code': 'ConditionalCheckFailed' if winner is not None else 'None'}])
            self.get('cases', 'offline-db', winner)
            if winner is None:
                self.get('clients', ACTIVE, current_client)
            if expected:
                with self.assertRaises(expected):
                    self.create()
            else:
                self.assertEqual(self.create(), (winner, False))

    def test_transaction_infrastructure_errors_never_become_business_conflict(self):
        for error, reasons in (
                ('TransactionCanceledException', None),
                ('TransactionCanceledException', [{'Code': 'ConditionalCheckFailed'}, {'Code': 'ThrottlingError'}]),
                ('TransactionCanceledException', [{'Code': 'TransactionConflict'}, {'Code': 'None'}]),
                ('AccessDeniedException', None), ('ProvisionedThroughputExceededException', None)):
            self.get('cases', 'offline-db', None)
            self.get('clients', ACTIVE, client())
            self.transaction(error=error, reasons=reasons)
            with self.assertRaises(Exception) as caught:
                self.create()
            self.assertNotIsInstance(caught.exception, (Conflict, NotFound))

    def test_stored_data_validation(self):
        for changes in ({'status': 'closed'}, {'created_at': 'yesterday'}, {'created_at': '2026-10-19T12:00:00+02:00'},
                        {'metadata': []}, {'metadata': {'bad': {'a', 'b'}}}, {'client_id': 'wrong'}):
            self.get('cases', 'offline-db', case(**changes))
            self.invoke('/cases/{case_id}', params={'case_id': 'offline-db'}, expected=500)
        for changes in ({'ico': 'bad'}, {'status': 'unknown'}, {'contacts': [{} , None]},
                        {'signatories': [{'authorized': 'yes'}]}, {'kyc': {'status': 'wrong'}},
                        {'contacts': [{'email': 'not-an-email'}]},
                        {'kyc': {'checked_at': '20261019'}},
                        {'source': 'live'}, {'name': None}):
            self.scan([client(**changes)], limit=50)
            self.invoke(expected=500)

    def test_read_errors_are_sanitized(self):
        for code in ('AccessDeniedException', 'ResourceNotFoundException',
                     'ProvisionedThroughputExceededException', 'InternalServerError', 'UnknownError'):
            self.stub.add_client_error('get_item', service_error_code=code, service_message='secret',
                expected_params={'TableName': ENV['CASES_TABLE_NAME'],
                    'Key': {'case_id': {'S': 'offline-db'}}, 'ConsistentRead': True})
            self.invoke('/cases/{case_id}', params={'case_id': 'offline-db'}, expected=500)

    def test_timeouts_and_scan_query_errors_are_not_empty_success_or_logged(self):
        with patch('logging.Logger._log') as log:
            for error in (ReadTimeoutError(endpoint_url='secret'), EndpointConnectionError(endpoint_url='secret')):
                with patch.object(self.sdk, 'get_item', side_effect=error):
                    self.invoke('/cases/{case_id}', params={'case_id': 'offline-db'}, expected=500)
            for operation, query in (('scan', None), ('query', {'ico': '00000019'})):
                self.stub.add_client_error(operation, service_error_code='AccessDeniedException',
                                           service_message='secret')
                self.invoke(query=query, expected=500)
            log.assert_not_called()

    def test_timeout_after_transaction_has_no_recovery_or_retry(self):
        self.get('cases', 'offline-db', None)
        self.get('clients', ACTIVE, client())
        with patch.object(self.sdk, 'transact_write_items',
                          side_effect=ReadTimeoutError(endpoint_url='secret')) as write:
            self.invoke('/cases', 'POST', body=json.dumps({'case_id': 'offline-db',
                        'client_id': ACTIVE}), expected=500)
            write.assert_called_once()

    def test_transaction_permission_failure_is_sanitized_by_handler(self):
        self.get('cases', 'offline-db', None)
        self.get('clients', ACTIVE, client())
        self.transaction(error='AccessDeniedException')
        with patch('case_client_dynamodb_repository.datetime') as clock:
            clock.now.return_value = datetime(2026, 10, 19, 12, tzinfo=timezone.utc)
            self.invoke('/cases', 'POST', body=json.dumps({'case_id': 'offline-db',
                        'client_id': ACTIVE}), expected=500)

    def test_unicode_metadata_boundary_and_all_optional_fields(self):
        metadata = {'x': 'á' * ((16384 - 8) // 2)}
        self.get('cases', 'offline-db', None)
        self.get('clients', ACTIVE, client())
        self.transaction(metadata)
        self.assertEqual(self.create(metadata), (case(metadata=metadata), True))
        stored = case()
        stored.pop('metadata')
        self.get('cases', 'offline-db', stored)
        self.assertEqual(self.repo.get_case('offline-db'), stored)
        stored_client = client(dic='CZ00000019', legal_form='s.r.o.', address='Test', source='synthetic',
            contacts=[{'name': 'A', 'role': 'B', 'email': 'a@example.test', 'phone': '123', 'preferred_channel': 'email'}],
            signatories=[{'name': 'A', 'function': 'jednatel', 'authorized': True}], kyc={'status': 'pending'})
        self.scan([stored_client], limit=50)
        self.assertEqual(self.invoke()['clients'], [stored_client])

    def test_direct_finite_float_is_serialized_as_json_number(self):
        self.get('cases', 'offline-db', None)
        self.get('clients', ACTIVE, client())
        self.transaction({'n': Decimal('1.25')})
        self.assertEqual(self.create({'n': 1.25}), (case(metadata={'n': Decimal('1.25')}), True))

    def test_client_read_respects_insufficient_list_time_budget(self):
        with self.assertRaises(RuntimeError):
            self.repository(time_remaining=lambda: 1).list_client_cases(ACTIVE, {}, 50)

    def test_direct_metadata_rejected_without_writes(self):
        for metadata in ([], {'x': 'á' * 8192}, {'n': float('nan')}, {'n': Decimal('1e999')},
                         {'n': Decimal('1e126')}, {'n': Decimal('1e-131')},
                         {'n': Decimal('NaN')}, {'n': Decimal('Infinity')},
                         {'n': Decimal('0.123456789012345678901234567890123456789')}, {'n': {'set'}}):
            with self.assertRaises(InvalidRequest):
                self.create(metadata)
