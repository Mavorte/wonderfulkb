import base64
import copy
import json
from datetime import datetime
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft7Validator, FormatChecker
from referencing import Registry, Resource

from test_monitor_file_received import intake  # noqa: F401
from test_processing_monitor_routes import monitor, event, get, RUN_URL, URL, HEADERS  # noqa: F401
from document_processing.audit.audit_queries import document_key

ATTEMPTS = RUN_URL.removesuffix('/events') + '/attempts'
KEY = {'pk': document_key('case-test', 'doc-test'), 'sk': 'EVENT#other'}


def test_observed_attempts_without_run_queued(monitor):
    main, _, _, _, _, table = monitor
    table.query.return_value = {'Items': [
        event('a1', type='AttemptStarted', run_id='run-a', attempt_no=1),
        event('b1', type='AttemptStarted', run_id='run-b', attempt_no=1),
        event('a2', type='AttemptStarted', run_id='run-a', attempt_no=2),
        event('conflict', type='AttemptStarted', run_id='run-a', attempt_no=2), event('received')]}
    response = get(main, ATTEMPTS)
    assert response.status_code == 200
    body = response.json()
    assert body['items'] == [{'event_id': key, 'attempt_no': number, 'occurred_at': '2026-10-20T10:00:00Z'}
                             for key, number in [('a1', 1), ('a2', 2), ('conflict', 2)]]
    assert body['coverage'] == 'partial' and body['next_token'] is None
    assert datetime.fromisoformat(body['observed_at'].replace('Z', '+00:00')).utcoffset().total_seconds() == 0
    table.query.assert_called_once()
    table.scan.assert_not_called()


def test_bounded_empty_continuation_and_operation_isolation(monitor):
    main, _, _, _, _, table = monitor
    table.query.side_effect = [
        {'Items': [event()], 'LastEvaluatedKey': KEY},
        {'Items': [event('a1', type='AttemptStarted', run_id='run-a', attempt_no=1)]}]
    first = get(main, ATTEMPTS, params={'limit': 1})
    assert first.status_code == 200
    assert first.json()['items'] == []
    token = first.json()['next_token']
    assert token and table.query.call_count == 1
    for target in (RUN_URL, URL, ATTEMPTS.replace('run-a', 'run-b')):
        assert get(main, target, params={'next_token': token}).status_code == 400
    assert table.query.call_count == 1
    second = get(main, ATTEMPTS, params={'limit': 1, 'next_token': token})
    assert second.status_code == 200 and second.json()['items'][0]['event_id'] == 'a1'
    assert second.json()['next_token'] is None
    assert table.query.call_count == 2
    assert table.query.call_args.kwargs['ExclusiveStartKey'] == KEY
    assert table.query.call_args.kwargs['Limit'] == 1
    table.query.side_effect = None
    table.query.return_value = {'Items': [], 'LastEvaluatedKey': KEY}
    for source in (RUN_URL, URL):
        foreign = get(main, source).json()['next_token']
        before = table.query.call_count
        assert get(main, ATTEMPTS, params={'next_token': foreign}).status_code == 400
        assert table.query.call_count == before
    table.scan.assert_not_called()


@pytest.mark.parametrize('change', ['case_id', 'document_id', 'run_id', 'operation', 'version', 'reader',
    'extra', 'duplicate', 'bad', 'oversize', 'inner-oversize', 'inner-scope', 'padding'])
def test_cursor_rejected_before_query(monitor, change):
    main, _, _, _, _, table = monitor
    table.query.return_value = {'Items': [], 'LastEvaluatedKey': KEY}
    response = get(main, ATTEMPTS)
    assert response.status_code == 200
    token = response.json()['next_token']
    data = json.loads(base64.urlsafe_b64decode(token + '=' * (-len(token) % 4)))
    if change in {'case_id', 'document_id', 'run_id', 'operation'}: data[change] = 'foreign'
    if change == 'version': data[change] = True
    if change == 'reader': data[change] = 1
    if change == 'extra': data['extra'] = 1
    if change == 'inner-oversize': data['reader'] = 'a' * 4097
    if change == 'inner-scope':
        inner = json.loads(base64.urlsafe_b64decode(data['reader'] + '=' * (-len(data['reader']) % 4)))
        inner['document_id'] = 'foreign'
        data['reader'] = base64.urlsafe_b64encode(json.dumps(inner).encode()).decode().rstrip('=')
    raw = json.dumps(data)
    if change == 'duplicate': raw = raw[:-1] + ', "version": 1}'
    token = base64.urlsafe_b64encode(raw.encode()).decode().rstrip('=')
    if change == 'bad': token = 'bad'
    if change == 'oversize': token = 'a' * 8193
    if change == 'padding': token += '='
    table.reset_mock()
    assert get(main, ATTEMPTS, params={'next_token': token}).status_code == 400
    table.query.assert_not_called()


@pytest.mark.parametrize('failure,status', [('missing-auth',403), ('forged',403), ('revoked',403),
    ('missing',404), ('foreign',404), ('auth',503), ('membership',503), ('read',503), ('decode',503), ('dto',503)])
def test_auth_scope_read_and_dto_failure(monitor, monkeypatch, failure, status):
    main, _, docs, source, policy, table = monitor
    headers = HEADERS
    if failure == 'missing-auth': headers = {}
    if failure == 'forged': headers = {'Authorization': 'Bearer forged'}
    if failure == 'revoked': policy['principals'][0]['case_ids'] = []
    if failure == 'missing': docs.get_item.return_value = {}
    if failure == 'foreign': docs.get_item.return_value = {'Item': {'case_id':'foreign', 'document_id':'doc-test'}}
    if failure == 'auth': source.side_effect = RuntimeError('private detail')
    if failure == 'membership': docs.get_item.side_effect = RuntimeError('private detail')
    if failure == 'read': table.query.side_effect = RuntimeError('private detail')
    if failure == 'decode': table.query.return_value = {'Items': [event(type='Unknown')]}
    if failure == 'dto':
        import processing_monitor_routes
        table.query.return_value = {'Items': [event(type='AttemptStarted',run_id='run-a',attempt_no=1)]}
        monkeypatch.setattr(processing_monitor_routes, 'attempt_dto', lambda _: 1 / 0, raising=False)
    response = get(main, ATTEMPTS, headers=headers)
    assert response.status_code == status
    assert 'private detail' not in response.text
    if failure not in {'read', 'decode', 'dto'}: table.query.assert_not_called()
    if failure in {'missing-auth','forged','revoked','auth'}: docs.get_item.assert_not_called()


@pytest.mark.parametrize('limit', [1,100,0,101,'bad'])
def test_limits_and_unknown_run(monitor, limit):
    main, _, _, _, _, table = monitor
    response = get(main, ATTEMPTS, params={'limit':limit})
    assert response.status_code == (200 if limit in (1,100) else 400)
    if limit in (1,100):
        assert response.json()['items'] == [] and response.json()['next_token'] is None
        assert table.query.call_args.kwargs['Limit'] == limit
    else: table.query.assert_not_called()


def test_sole_contract_accepts_only_observation_dto(monitor):
    main, _, _, _, _, table = monitor
    table.query.return_value = {'Items': [event('a1',type='AttemptStarted',run_id='run-a',attempt_no=1)]}
    response = get(main, ATTEMPTS)
    assert response.status_code == 200
    contract = yaml.safe_load((Path(__file__).resolve().parents[2] / 'be-document-processing/contracts/openapi-processing-monitor.yaml').read_text())
    def convert(value):
        if isinstance(value, dict):
            result = {k:convert(v) for k,v in value.items() if k != 'nullable'}
            if value.get('nullable') and 'type' in result: result['type'] = [result['type'],'null']
            return result
        if isinstance(value,list): return [convert(v) for v in value]
        return value
    resource = Resource.from_contents({'$schema':'http://json-schema.org/draft-07/schema#', **convert(contract)})
    validator = Draft7Validator({'$ref':'urn:monitor#/components/schemas/AttemptCollection'},
        registry=Registry().with_resource('urn:monitor',resource), format_checker=FormatChecker())
    body = response.json()
    validator.validate(body)
    for field,value in [('status','running'),('total',1),('duration_ms',1),('attempt_no',0),('attempt_no',True),('occurred_at','invalid')]:
        invalid = copy.deepcopy(body)
        invalid['items'][0][field] = value
        assert list(validator.iter_errors(invalid))
    for field in ('event_id','attempt_no','occurred_at'):
        invalid = copy.deepcopy(body)
        del invalid['items'][0][field]
        assert list(validator.iter_errors(invalid))
