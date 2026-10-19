"""Bounded in-place deployment of this component to the one test Lambda.

Private backup/state never enters the public evidence directory. No API/IAM
mutation is performed by this tool. Run from the repository root.
"""
import argparse
import base64
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import json
import logging
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import time
from urllib.request import build_opener, HTTPRedirectHandler
import zipfile

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

ACCOUNT = '609394381050'
REGION = 'eu-central-1'
PROFILE = 'ai-hackathon'
FUNCTION = f'arn:aws:lambda:{REGION}:{ACCOUNT}:function:wonderfulkb-case-client'
ROLE = f'arn:aws:iam::{ACCOUNT}:role/wonderfulkb-lambda-role'
API = 'bgm7k1ggqi'
URL = f'https://{API}.execute-api.{REGION}.amazonaws.com/v1'
TASK = 'task-beca6825-147b-43d9-9fb6-694368e70948'
ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / 'plans/checkpoints/case-client-live-integration' / TASK
MANIFEST = EVIDENCE / 'manifest.json'
# Deterministic private pointer, containing only a private temp directory path.
POINTER = Path('/tmp') / (TASK + '.private-path')
BINDINGS = {'DATA_BACKEND': 'dynamodb', 'ALLOW_EPHEMERAL_MOCK': 'false',
            'CLIENTS_TABLE_NAME': 'wonderfulkb-uw-clients',
            'CASES_TABLE_NAME': 'wonderfulkb-uw-cases',
            'CLIENTS_ICO_INDEX_NAME': 'ico-index',
            'CASES_CLIENT_CREATED_INDEX_NAME': 'client-created-index'}
CONFIG = Config(connect_timeout=3, read_timeout=15,
                retries={'total_max_attempts': 1}, max_pool_connections=2)


def validate_target(profile, account, region, function):
    if (profile, account, region, function) != (PROFILE, ACCOUNT, REGION, FUNCTION):
        raise ValueError('Target allowlist mismatch')


def require_revision(*, expected, actual):
    if not expected or expected != actual:
        raise ValueError('Concurrent revision change: stopped')


def require_writes(*, allow_writes=False, run_id=''):
    if not allow_writes or not re.fullmatch(r'[a-zA-Z0-9-]{8,64}', run_id):
        raise ValueError('Writes require explicit opt-in and a unique run-id')


class UnexpectedHTTP(AssertionError):
    def __init__(self, expected, actual):
        self.expected, self.actual = int(expected), int(actual)


def safe_error(error):
    # Never render exception messages, response headers, URLs or payloads.
    if isinstance(error, UnexpectedHTTP):
        return f'HTTP expected {error.expected}, received {error.actual}'
    if isinstance(error, ClientError):
        code = error.response.get('Error', {}).get('Code')
        if code in {'AccessDenied', 'AccessDeniedException', 'ExpiredToken',
                    'ExpiredTokenException', 'UnauthorizedException',
                    'PreconditionFailedException', 'ResourceConflictException',
                    'NotFoundException', 'ResourceNotFoundException'}:
            return code
        return 'AWS operation failed'
    if isinstance(error, AssertionError):
        return 'Scenario assertion failed'
    if type(error) is ValueError and str(error) in {
            'Concurrent revision change: stopped', 'Backup hash mismatch',
            'Lambda update unsuccessful', 'Missing compatible simplejson extension',
            'Wrong extension architecture', 'Task-wide budget exhausted',
            'Live deadline exhausted', 'Deployed config mismatch',
            'Deployed bindings mismatch', 'Rollback configuration mismatch',
            'Rollback environment mismatch'}:
        return str(error)
    return 'Operation blocked (' + type(error).__name__ + ')'


def private_write(path, data):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        os.fchmod(stream.fileno(), 0o600)
        stream.write(data)


def digest(data):
    return base64.b64encode(hashlib.sha256(data).digest()).decode()


def verify_backup(data, expected):
    if digest(data) != expected:
        raise ValueError('Backup hash mismatch')


def load_manifest():
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text())
    return {'task_id': TASK, 'account': ACCOUNT, 'region': REGION,
            'function': FUNCTION, 'api_url': URL, 'deploy_attempts': 0,
            'post_attempts': 0, 'fixtures': [], 'case_ids': [],
            'scenarios': {}, 'rollback': 'not-needed', 'status': 'IN_PROGRESS'}


def save_manifest(m):
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    temporary = MANIFEST.with_suffix('.tmp')
    temporary.write_text(json.dumps(m, indent=2, sort_keys=True) + '\n')
    temporary.replace(MANIFEST)


def reserve(m, kind, limit, *, recovery=False):
    continuation = m.get('continuation_id') == 'case-live-beca6825-20261019-iam1750'
    effective_limit = limit
    if continuation and kind == 'deploy_attempts':
        effective_limit = 4 if recovery else 3
    elif continuation and kind == 'post_attempts':
        effective_limit = 6
    if m.get(kind, 0) >= effective_limit:
        raise ValueError('Task-wide budget exhausted')
    if not recovery:
        duration = 1800 if continuation else 3600
        if time.time() - m.setdefault('live_started_at', time.time()) >= duration:
            raise ValueError('Live deadline exhausted')
    m[kind] = m.get(kind, 0) + 1
    save_manifest(m)  # reserve before mutation, including ambiguous outcomes


def session():
    for name in ('boto3', 'botocore', 'urllib3'):
        logging.getLogger(name).disabled = True
    return boto3.Session(profile_name=PROFILE, region_name=REGION)


def identity(s):
    account = s.client('sts', config=CONFIG).get_caller_identity()['Account']
    validate_target(s.profile_name, account, s.region_name, FUNCTION)


def binding_readback(c):
    return {k: c.get(k) for k in ('Runtime', 'Handler', 'Role', 'Architectures',
                                 'CodeSha256', 'LastUpdateStatus')} | {
        'bindings': {k: c.get('Environment', {}).get('Variables', {}).get(k)
                     for k in BINDINGS}}


def preflight(s):
    identity(s)
    lc = s.client('lambda', config=CONFIG)
    f = lc.get_function(FunctionName=FUNCTION)
    c = f['Configuration']
    if c['FunctionArn'] != FUNCTION or c['Role'] != ROLE or c.get('PackageType') != 'Zip':
        raise ValueError('Unexpected Lambda target')
    ddb = s.client('dynamodb', config=CONFIG)
    schemas = [('wonderfulkb-uw-clients', 'client_id', 'ico-index',
                [{'AttributeName': 'ico', 'KeyType': 'HASH'}]),
               ('wonderfulkb-uw-cases', 'case_id', 'client-created-index',
                [{'AttributeName': 'client_id', 'KeyType': 'HASH'},
                 {'AttributeName': 'created_at', 'KeyType': 'RANGE'}])]
    for table, key, index, keys in schemas:
        t = ddb.describe_table(TableName=table)['Table']
        if (t['TableArn'] != f'arn:aws:dynamodb:{REGION}:{ACCOUNT}:table/{table}'
                or t['TableStatus'] != 'ACTIVE'
                or t['KeySchema'] != [{'AttributeName': key, 'KeyType': 'HASH'}]):
            raise ValueError('Unexpected table binding')
        i = next(i for i in t['GlobalSecondaryIndexes'] if i['IndexName'] == index)
        if i['KeySchema'] != keys or i['Projection']['ProjectionType'] != 'ALL' or i['IndexStatus'] != 'ACTIVE':
            raise ValueError('Unexpected index binding')
    api = s.client('apigateway', config=CONFIG)
    resources = [i for page in api.get_paginator('get_resources').paginate(
        restApiId=API, embed=['methods']) for i in page['items']]
    routes = {'/clients': 'GET', '/cases': 'POST', '/cases/{case_id}': 'GET',
              '/clients/{client_id}/cases': 'GET'}
    methods = []
    for path, method in routes.items():
        r = next(i for i in resources if i['path'] == path)
        detail = api.get_method(restApiId=API, resourceId=r['id'], httpMethod=method)
        integration = detail['methodIntegration']
        if (not detail.get('apiKeyRequired') or detail['authorizationType'] != 'NONE'
                or integration['type'] != 'AWS_PROXY' or integration['httpMethod'] != 'POST'
                or integration['uri'] != f'arn:aws:apigateway:{REGION}:lambda:path/2015-03-31/functions/{FUNCTION}/invocations'):
            raise ValueError('Unexpected API integration/auth')
        methods.append({'path': path, 'method': method, 'snapshot': detail})
    stage = api.get_stage(restApiId=API, stageName='v1')
    policy = lc.get_policy(FunctionName=FUNCTION)['Policy']
    return f, {'methods': methods, 'stage': stage, 'lambda_policy': policy}


def private_state():
    if not POINTER.exists() or POINTER.is_symlink() or POINTER.stat().st_mode & 0o077:
        raise ValueError('Private state unavailable')
    directory = Path(POINTER.read_text())
    if directory.is_symlink() or directory.stat().st_mode & 0o077:
        raise ValueError('Private state permissions')
    return directory, json.loads((directory / 'state.json').read_text())


def store_state(directory, state):
    private_write(directory / 'state.json', json.dumps(state, default=str).encode())


class NoDownloadRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def snapshot(f, api_snapshot):
    if POINTER.exists():
        return private_state()
    directory = Path(tempfile.mkdtemp(prefix='case-client-', dir='/tmp'))
    os.chmod(directory, 0o700)
    with build_opener(NoDownloadRedirect()).open(f['Code']['Location'], timeout=30) as response:
        data = response.read(60 * 1024 * 1024)
    verify_backup(data, f['Configuration']['CodeSha256'])
    private_write(directory / 'original.zip', data)
    state = {'original': f['Configuration'], 'api': api_snapshot,
             'revision': f['Configuration']['RevisionId'], 'mutated': False}
    store_state(directory, state)
    private_write(POINTER, str(directory).encode())
    return directory, state


def build(directory):
    staging = directory / 'package'
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(mode=0o700)
    if importlib.util.find_spec('pip'):
        command = [sys.executable, '-m', 'pip', 'install', '--disable-pip-version-check',
            '--platform', 'manylinux2014_x86_64', '--implementation', 'cp',
            '--python-version', '3.13', '--abi', 'cp313', '--only-binary=:all:']
    else:
        uv = shutil.which('uv')
        if not uv:
            raise ValueError('Build requires existing pip or uv')
        command = [uv, 'pip', 'install', '--python', sys.executable,
            '--python-version', '3.13', '--python-platform', 'x86_64-manylinux2014',
            '--only-binary', ':all:']
    subprocess.run(command + ['--target', str(staging), '-r',
        str(ROOT / 'be-case-client/src/requirements.txt')],
        check=True, timeout=240, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for p in (ROOT / 'be-case-client/src').glob('*.py'):
        shutil.copyfile(p, staging / p.name)
    extensions = list((staging / 'simplejson').glob('*.so'))
    if len(extensions) != 1 or 'cpython-313-x86_64-linux-gnu' not in extensions[0].name:
        raise ValueError('Missing compatible simplejson extension')
    elf = extensions[0].read_bytes()
    if elf[:5] != b'\x7fELF\x02' or struct.unpack('<H', elf[18:20])[0] != 62:
        raise ValueError('Wrong extension architecture')
    artifact = directory / 'python.zip'
    with zipfile.ZipFile(artifact, 'w', zipfile.ZIP_DEFLATED) as archive:
        for p in sorted(staging.rglob('*')):
            if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc':
                relative = p.relative_to(staging)
                # Retain pinned SDK packages and common endpoint/partition data,
                # but ship only the service models used by this Lambda and its
                # credential provider. This also bounds direct upload payloads.
                parts = relative.parts
                if (len(parts) > 3 and parts[:2] in (('botocore', 'data'), ('boto3', 'data'))
                        and parts[2] not in ('dynamodb', 'sts')):
                    continue
                archive.write(p, relative)
    os.chmod(artifact, 0o600)
    data = artifact.read_bytes()
    if len(data) >= 50 * 1024 * 1024:
        raise ValueError('Direct upload size exceeded')
    return data


def updated(lc, response):
    lc.get_waiter('function_updated_v2').wait(FunctionName=FUNCTION,
        WaiterConfig={'Delay': 2, 'MaxAttempts': 45})
    c = lc.get_function_configuration(FunctionName=FUNCTION)
    if c['LastUpdateStatus'] != 'Successful':
        raise ValueError('Lambda update unsuccessful')
    if c['RevisionId'] != response['RevisionId']:
        # Lambda can finalize an asynchronous update with a second RevisionId.
        # Accept only the exact returned operation's timestamp, hash and config;
        # use the final read-back RevisionId for the next conditional mutation.
        for key in ('LastModified', 'CodeSha256', 'Runtime', 'Handler', 'Role', 'Architectures'):
            if key not in response or c.get(key) != response[key]:
                raise ValueError('Concurrent revision change: stopped')
        if c.get('Environment', {}).get('Variables', {}) != response.get('Environment', {}).get('Variables', {}):
            raise ValueError('Concurrent revision change: stopped')
    return c


def apply_update(s, directory, state, data, config, architectures):
    identity(s)
    lc = s.client('lambda', config=CONFIG)
    current = lc.get_function_configuration(FunctionName=FUNCTION)
    require_revision(expected=state['revision'], actual=current['RevisionId'])
    reply = lc.update_function_code(FunctionName=FUNCTION, ZipFile=data,
        Architectures=architectures, RevisionId=state['revision'])
    state.update(revision=reply['RevisionId'], mutated=True, pending_response=reply)
    store_state(directory, state)
    c = updated(lc, reply)
    state['revision'] = c['RevisionId']
    store_state(directory, state)
    identity(s)
    reply = lc.update_function_configuration(FunctionName=FUNCTION,
        RevisionId=state['revision'], **config)
    state.update(revision=reply['RevisionId'], pending_response=reply)
    store_state(directory, state)
    c = updated(lc, reply)
    state['revision'] = c['RevisionId']
    state.pop('pending_response', None)
    store_state(directory, state)
    verify_backup(data, c['CodeSha256'])
    return c


def resume_configuration(s, directory, state, config):
    """Recover this task's known successful code upload, never a foreign update."""
    lc = s.client('lambda', config=CONFIG)
    current = lc.get_function_configuration(FunctionName=FUNCTION)
    data = (directory / 'python.zip').read_bytes()
    verify_backup(data, current['CodeSha256'])
    response = state.get('pending_response')
    if response is None:
        # Compatibility with the first live attempt, which persisted RevisionId
        # but not the asynchronous response. Use CloudTrail, never guess ownership.
        trail = s.client('cloudtrail', config=CONFIG)
        events = [json.loads(e['CloudTrailEvent'])
            for page in trail.get_paginator('lookup_events').paginate(
                LookupAttributes=[{'AttributeKey': 'EventSource', 'AttributeValue': 'lambda.amazonaws.com'}],
                StartTime=datetime.now(timezone.utc) - timedelta(hours=1)) for e in page['Events']]
        writes = [e for e in events if e.get('eventName', '').startswith('UpdateFunction')
                  and (e.get('requestParameters') or {}).get('functionName') in (FUNCTION, FUNCTION.split(':')[-1])
                  and not e.get('errorCode')]
        writes.sort(key=lambda e: e['eventTime'], reverse=True)
        if not writes:
            raise ValueError('Concurrent revision change: stopped')
        event = writes[0]
        r = event.get('responseElements') or {}
        if (not event['eventName'].startswith('UpdateFunctionCode')
                or r.get('revisionId') != state['revision']
                or r.get('lastModified') != current['LastModified']
                or r.get('codeSha256') != digest(data)):
            raise ValueError('Concurrent revision change: stopped')
        for key in ('Runtime', 'Handler', 'Role'):
            if current[key] != state['original'][key]:
                raise ValueError('Concurrent revision change: stopped')
        if current.get('Environment', {}).get('Variables', {}) != state['original'].get('Environment', {}).get('Variables', {}):
            raise ValueError('Concurrent revision change: stopped')
    else:
        current = updated(lc, response)
    state['revision'] = current['RevisionId']
    store_state(directory, state)
    identity(s)
    reply = lc.update_function_configuration(FunctionName=FUNCTION,
        RevisionId=state['revision'], **config)
    state.update(revision=reply['RevisionId'], pending_response=reply)
    store_state(directory, state)
    c = updated(lc, reply)
    state['revision'] = c['RevisionId']
    state.pop('pending_response', None)
    store_state(directory, state)
    verify_backup(data, c['CodeSha256'])
    return c


def run(args):
    s = session()
    m = load_manifest()
    f, api_snapshot = preflight(s)
    m['observed'] = binding_readback(f['Configuration'])
    m['api_preflight'] = 'PASS: four original protected AWS_PROXY methods'
    if args.action == 'preflight':
        if POINTER.exists():
            _, state = private_state()
            m['owned_revision'] = state['revision']
        save_manifest(m)
        return
    if args.action == 'verify':
        directory, state = private_state()
        c = f['Configuration']
        require_revision(expected=state['revision'], actual=c['RevisionId'])
        verify_backup((directory / 'python.zip').read_bytes(), c['CodeSha256'])
        if (c['Runtime'], c['Handler'], c['Role'], c['Architectures']) != (
                'python3.13', 'case_client_handler.lambda_handler', ROLE, ['x86_64']):
            raise ValueError('Deployed config mismatch')
        if any(c.get('Environment', {}).get('Variables', {}).get(k) != v for k, v in BINDINGS.items()):
            raise ValueError('Deployed bindings mismatch')
        m['post_live'] = binding_readback(c)
        save_manifest(m)
        return
    require_writes(allow_writes=args.allow_writes, run_id=args.run_id)
    if args.action in ('deploy', 'resume-config') and not m.get('original_http_baseline', '').startswith('PASS'):
        raise ValueError('Original HTTP baseline required before deployment')
    directory, state = snapshot(f, api_snapshot)
    m.setdefault('original', binding_readback(state['original']))
    if args.action == 'rollback':
        reserve(m, 'deploy_attempts', 5, recovery=True)
        original = state['original']
        data = (directory / 'original.zip').read_bytes()
        verify_backup(data, original['CodeSha256'])
        restore = {k: original[k] for k in ('Runtime', 'Handler', 'Role')}
        restore['Environment'] = original.get('Environment', {'Variables': {}})
        c = apply_update(s, directory, state, data, restore,
            original['Architectures'])
        for key in ('Runtime', 'Handler', 'Role', 'Architectures', 'CodeSha256'):
            if c[key] != original[key]:
                raise ValueError('Rollback configuration mismatch')
        if c.get('Environment', {}).get('Variables', {}) != original.get('Environment', {}).get('Variables', {}):
            raise ValueError('Rollback environment mismatch')
        m.update(rollback='restored-code-and-config-awaiting-http', restored=binding_readback(c), status='BLOCKED')
    else:
        reserve(m, 'deploy_attempts', 4)  # fifth slot reserved for recovery
        data = (directory / 'python.zip').read_bytes() if args.action == 'resume-config' else build(directory)
        m['artifact_sha256'] = hashlib.sha256(data).hexdigest()
        m['artifact_code_sha256'] = digest(data)
        m['artifact_bytes'] = len(data)
        # A fresh deployment invalidates cached scenario passes, never budgets.
        m['scenarios'] = {}
        save_manifest(m)
        env = dict(state['original'].get('Environment', {}).get('Variables', {}))
        env.update(BINDINGS)
        config = {'Runtime': 'python3.13', 'Handler': 'case_client_handler.lambda_handler',
                  'Environment': {'Variables': env}, 'Role': ROLE}
        if args.action == 'resume-config':
            c = resume_configuration(s, directory, state, config)
            m['revision_reconciliation'] = 'Own code upload verified against latest CloudTrail update, hash, timestamp and unchanged original config; finalized revision used conditionally.'
        else:
            c = apply_update(s, directory, state, data, config, ['x86_64'])
        m['pre_live'] = binding_readback(c)
    save_manifest(m)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['preflight', 'deploy', 'resume-config', 'verify', 'rollback'])
    parser.add_argument('--allow-writes', action='store_true')
    parser.add_argument('--run-id', default='')
    args = parser.parse_args()
    try:
        run(args)
        print(json.dumps({'action': args.action, 'result': 'PASS'}))
        return 0
    except Exception as error:
        m = load_manifest()
        m.update(status='BLOCKED', blocker=safe_error(error), blocked_action=args.action)
        save_manifest(m)
        print(json.dumps({'action': args.action, 'result': 'BLOCKED', 'error': safe_error(error)}))
        return 1


if __name__ == '__main__':
    sys.exit(main())
