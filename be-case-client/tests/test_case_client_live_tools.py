"""Offline live-tool safety contracts; sockets and discovery are forbidden."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from unittest.mock import Mock
import os
import tempfile
from urllib.error import URLError
from botocore.exceptions import ClientError

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'tests' / 'integration')]
from case_client_test_deploy import validate_target, require_revision
from case_client_api_integration import require_writes, safe_error, NoRedirect
import case_client_test_deploy as deploy
import case_client_api_integration as api


class LiveToolGuards(unittest.TestCase):
    def setUp(self):
        for name in ('socket.socket', 'socket.getaddrinfo'):
            guard = patch(name, side_effect=AssertionError('network forbidden'))
            guard.start()
            self.addCleanup(guard.stop)

    def test_wrong_account_rejected(self):
        with self.assertRaises(ValueError):
            validate_target('ai-hackathon', '000000000000', 'eu-central-1',
                'arn:aws:lambda:eu-central-1:609394381050:function:wonderfulkb-case-client')

    def test_write_requires_run_id(self):
        with self.assertRaises(ValueError):
            require_writes(allow_writes=True, run_id='')

    def test_changed_revision_rejected(self):
        with self.assertRaises(ValueError):
            require_revision(expected='ours', actual='someone-else')

    def test_secret_exception_redacted(self):
        self.assertNotIn('fake-key-for-offline-test',
            safe_error(RuntimeError('fake-key-for-offline-test')))

    def test_no_redirect_request(self):
        self.assertIsNone(NoRedirect().redirect_request(
            None, None, 302, 'Found', {}, 'https://example.invalid/'))

    def test_deadline_rechecked_after_rate_limit_wait(self):
        now = [100.0]

        def sleep(seconds):
            now[0] += seconds

        http = api.Transport('fake-key', clock=lambda: now[0], sleep=sleep)
        http.deadline = 100.1
        http.next_start = 100.55
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.read.return_value = b'{}'
        response.code = 200
        response.headers = {}
        opener = Mock()
        opener.open.return_value = response
        with patch.object(api, 'build_opener', return_value=opener):
            with self.assertRaisesRegex(ValueError, 'deadline'):
                http.request('GET', '/clients')
        opener.open.assert_not_called()

    def test_all_target_dimensions_and_url_fail_closed(self):
        target = [deploy.PROFILE, deploy.ACCOUNT, deploy.REGION, deploy.FUNCTION]
        deploy.validate_target(*target)
        for index in range(4):
            wrong = target.copy()
            wrong[index] = 'wrong'
            with self.subTest(index=index), self.assertRaises(ValueError):
                deploy.validate_target(*wrong)
        for url in ('http://example.invalid', deploy.URL + '/', deploy.URL + '@example.invalid'):
            with self.assertRaises(ValueError):
                api.Transport('fake-key', url=url)

    def test_timeout_uses_budget_remaining_after_limiter(self):
        now = [100.0]
        http = api.Transport('fake-key', clock=lambda: now[0],
                             sleep=lambda seconds: now.__setitem__(0, now[0] + seconds))
        http.deadline = 101
        http.next_start = 100.55
        opener = Mock()
        opener.open.side_effect = URLError('offline')
        with patch.object(api, 'build_opener', return_value=opener), self.assertRaises(URLError):
            http.request('GET', '/clients')
        self.assertAlmostEqual(opener.open.call_args.kwargs['timeout'], .45)

    def test_continuation_budget_keeps_reserved_rollback(self):
        m = {'continuation_id': 'case-live-beca6825-20261019-iam1750',
             'live_started_at': 100, 'deploy_attempts': 2}
        with patch.object(deploy.time, 'time', return_value=101), patch.object(deploy, 'save_manifest'):
            deploy.reserve(m, 'deploy_attempts', 4)
            with self.assertRaises(ValueError):
                deploy.reserve(m, 'deploy_attempts', 4)
            deploy.reserve(m, 'deploy_attempts', 4, recovery=True)
            with self.assertRaises(ValueError):
                deploy.reserve(m, 'deploy_attempts', 4, recovery=True)

    def test_continuation_deadline_is_thirty_minutes(self):
        m = {'continuation_id': 'case-live-beca6825-20261019-iam1750', 'live_started_at': 100}
        with patch.object(deploy.time, 'time', return_value=1900), \
                patch.object(deploy, 'save_manifest'), self.assertRaisesRegex(ValueError, 'deadline'):
            deploy.reserve(m, 'post_attempts', 6)

    def test_default_write_denied_and_run_id_validated(self):
        for kwargs in ({}, {'allow_writes': False, 'run_id': 'valid-run-id'},
                       {'allow_writes': True, 'run_id': '../bad-id'}):
            with self.assertRaises(ValueError):
                require_writes(**kwargs)
        require_writes(allow_writes=True, run_id='valid-run-id')

    def test_sdk_exception_redaction_in_stdout_and_manifest(self):
        secret = 'fake-key-for-offline-test'
        error = ClientError({'Error': {'Code': 'AccessDeniedException', 'Message': secret},
                             'ResponseMetadata': {'HTTPHeaders': {'x-api-key': secret}}}, secret)
        self.assertEqual(safe_error(error), 'AccessDeniedException')
        import io
        output = io.StringIO()
        with patch.object(deploy, 'run', side_effect=error), patch.object(deploy, 'save_manifest') as save, \
                patch.object(deploy, 'load_manifest', return_value={}), \
                patch.object(sys, 'argv', ['tool', 'preflight']), \
                patch('sys.stdout', output), patch('sys.stderr', output):
            self.assertEqual(deploy.main(), 1)
        self.assertNotIn(secret, output.getvalue())
        self.assertNotIn(secret, str(save.call_args))

    def test_backup_hash_and_private_permissions(self):
        data = b'original-zip'
        deploy.verify_backup(data, deploy.digest(data))
        with self.assertRaises(ValueError):
            deploy.verify_backup(data, deploy.digest(b'wrong'))
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root) / 'backup'
            folder.mkdir(mode=0o700)
            target = folder / 'original.zip'
            deploy.private_write(target, data)
            self.assertEqual(folder.stat().st_mode & 0o777, 0o700)
            self.assertEqual(target.stat().st_mode & 0o777, 0o600)
            self.assertEqual(target.read_bytes(), data)
            link = folder / 'link'
            link.symlink_to(target)
            with self.assertRaises(OSError):
                deploy.private_write(link, b'overwrite')
            self.assertEqual(target.read_bytes(), data)

    def test_update_revision_waiters_and_original_environment_restore(self):
        lc = Mock()
        s = Mock()
        s.client.return_value = lc
        lc.get_function_configuration.side_effect = [
            {'RevisionId': 'ours'},
            {'RevisionId': 'code-revision', 'LastUpdateStatus': 'Successful'},
            {'RevisionId': 'config-revision', 'LastUpdateStatus': 'Successful',
             'CodeSha256': deploy.digest(b'zip')}]
        lc.update_function_code.return_value = {'RevisionId': 'code-revision'}
        lc.update_function_configuration.return_value = {'RevisionId': 'config-revision'}
        with patch.object(deploy, 'identity'), patch.object(deploy, 'store_state'):
            state = {'revision': 'ours'}
            deploy.apply_update(s, Path('/unused'), state, b'zip',
                {'Runtime': 'nodejs22.x', 'Environment': {'Variables': {}}}, ['arm64'])
        self.assertEqual(lc.update_function_code.call_args.kwargs['RevisionId'], 'ours')
        self.assertEqual(lc.update_function_code.call_args.kwargs['Architectures'], ['arm64'])
        self.assertEqual(lc.update_function_configuration.call_args.kwargs['RevisionId'], 'code-revision')
        self.assertEqual(lc.get_waiter.return_value.wait.call_count, 2)
        self.assertEqual(state['revision'], 'config-revision')

    def test_concurrent_revision_prevents_deploy_or_rollback(self):
        s = Mock()
        lc = s.client.return_value
        lc.get_function_configuration.return_value = {'RevisionId': 'foreign'}
        with patch.object(deploy, 'identity'), self.assertRaises(ValueError):
            deploy.apply_update(s, Path('/unused'), {'revision': 'ours'}, b'zip', {}, ['x86_64'])
        lc.update_function_code.assert_not_called()
        lc.update_function_configuration.assert_not_called()

    def test_async_revision_finalization_requires_exact_operation_fingerprint(self):
        reply = {'RevisionId': 'accepted', 'LastModified': '2026-10-19T15:36:16.000+0000',
                 'CodeSha256': 'ours', 'Runtime': 'python3.13', 'Handler': 'handler',
                 'Role': deploy.ROLE, 'Architectures': ['x86_64'],
                 'Environment': {'Variables': deploy.BINDINGS}}
        final = reply | {'RevisionId': 'finalized', 'LastUpdateStatus': 'Successful'}
        lc = Mock()
        lc.get_function_configuration.return_value = final
        self.assertEqual(deploy.updated(lc, reply)['RevisionId'], 'finalized')
        for field, foreign in [('LastModified', 'foreign-time'), ('CodeSha256', 'foreign-hash'),
                               ('Handler', 'foreign-handler'), ('Environment', {'Variables': {}})]:
            lc.get_function_configuration.return_value = final | {field: foreign}
            with self.subTest(field=field), self.assertRaises(ValueError):
                deploy.updated(lc, reply)

    def test_task_wide_budgets_and_deadline(self):
        for kind, maximum in [('deploy_attempts', 5), ('post_attempts', 12), ('fixture_attempts', 4)]:
            m = {kind: maximum - 1}
            with patch.object(deploy, 'save_manifest') as save:
                deploy.reserve(m, kind, maximum)
                self.assertEqual(m[kind], maximum)
                with self.assertRaises(ValueError):
                    deploy.reserve(m, kind, maximum)
                self.assertEqual(save.call_count, 1)
        with patch.object(deploy.time, 'time', return_value=4000), \
                patch.object(deploy, 'save_manifest'), self.assertRaises(ValueError):
            deploy.reserve({'live_started_at': 0}, 'post_attempts', 12)
        with patch.object(deploy.time, 'time', return_value=4000), patch.object(deploy, 'save_manifest'):
            m = {'live_started_at': 0, 'deploy_attempts': 4}
            deploy.reserve(m, 'deploy_attempts', 5, recovery=True)
            self.assertEqual(m['deploy_attempts'], 5)

    def test_post_transport_never_retries_and_rate_is_shared(self):
        http = api.Transport('fake-key', clock=lambda: 100, sleep=Mock())
        opener = Mock()
        opener.open.side_effect = URLError('fake-key-for-offline-test')
        with patch.object(api, 'build_opener', return_value=opener):
            with self.assertRaises(URLError):
                http.request('POST', '/cases', body={'client_id': 'synthetic'})
        self.assertEqual(opener.open.call_count, 1)
        self.assertEqual(opener.open.call_args.kwargs['timeout'], 20)
        with patch.object(api, 'build_opener', return_value=opener), self.assertRaises(URLError):
            http.request('GET', '/clients')
        self.assertAlmostEqual(http.sleep.call_args.args[0], .55)

    def test_read_only_default_does_not_seed_or_post(self):
        args = Mock(allow_writes=False, baseline=False)
        m = {'scenarios': {}, 'artifact_code_sha256': 'our-code'}
        s = Mock()
        s.client.return_value.get_function_configuration.return_value = {
            'CodeSha256': 'our-code', 'Runtime': 'python3.13',
            'Handler': 'case_client_handler.lambda_handler', 'Role': deploy.ROLE,
            'Environment': {'Variables': deploy.BINDINGS}}
        with patch.object(api, 'session', return_value=s), patch.object(api, 'identity'), \
                patch.object(api, 'load_manifest', return_value=m), \
                patch.object(api, 'api_key', return_value='fake-key'), \
                patch.object(api, 'Transport'), patch.object(api, 'scenario'), \
                patch.object(api, 'save_manifest'), patch.object(api, 'write_matrix') as writes:
            api.run(args)
        writes.assert_not_called()
        self.assertNotIn('live_matrix', m)

    def test_key_is_discovered_through_stage_usage_plan_not_key_id(self):
        s = Mock()
        client = s.client.return_value
        client.get_usage_plan.return_value = {'apiStages': [{'apiId': deploy.API, 'stage': 'v1'}]}
        plans = Mock()
        plans.paginate.return_value = [{'items': [
            {'id': 'unrelated', 'apiStages': [{'apiId': 'other', 'stage': 'v1'}]},
            {'id': '0jpa4e', 'apiStages': [{'apiId': deploy.API, 'stage': 'v1'}]}]}]
        keys = Mock()
        keys.paginate.side_effect = lambda **kw: [{'items': [{'id': '16u2jtkay6'}]}] \
            if kw['usagePlanId'] == '0jpa4e' else [{'items': []}]
        client.get_paginator.side_effect = lambda name: plans if name == 'get_usage_plans' else keys
        client.get_api_key.return_value = {'enabled': True, 'value': 'fake-memory-only-key'}
        try:
            selected = api.api_key(s)
        except ValueError:
            selected = None
        self.assertEqual(selected, 'fake-memory-only-key')
        client.get_api_key.assert_called_once_with(apiKey='16u2jtkay6', includeValue=True)
