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

    def test_authorized_continuation_uses_fresh_exact_limits(self):
        manifest = {'continuation_id': 'case-global-72fa-20261019-1909'}
        self.assertEqual(deploy.CONTINUATIONS[manifest['continuation_id']], (4, 12, 3600))
        with patch.object(deploy, 'save_manifest'):
            for _ in range(3):
                deploy.reserve(manifest, 'deploy_attempts', 4)
            with self.assertRaises(ValueError):
                deploy.reserve(manifest, 'deploy_attempts', 4)
            deploy.reserve(manifest, 'deploy_attempts', 4, recovery=True)
        self.assertEqual(manifest['deploy_attempts'], 4)

    def test_authorized_continuation_uses_current_task_ledger(self):
        self.assertEqual(deploy.TASK, 'task-7700299e-f977-4acd-a1fe-b7409c3bca5d')

    def test_preflight_accepts_missing_get_only_before_deploy(self):
        self.assertTrue(callable(getattr(deploy, 'require_routes', None)), 'missing route validator')
        gateway = self.gateway()
        gateway.get_method.side_effect = self.method_missing_global
        deploy.require_routes(gateway, deployed=False)
        with self.assertRaises(ValueError):
            deploy.require_routes(gateway, deployed=True)

    def test_route_checks_preserve_both_cases_methods(self):
        self.assertTrue(callable(getattr(deploy, 'required_routes', None)), 'missing ordered five-route contract')
        routes = deploy.required_routes()
        self.assertEqual(routes, [('/clients', 'GET'), ('/cases', 'POST'), ('/cases', 'GET'),
                                 ('/cases/{case_id}', 'GET'), ('/clients/{client_id}/cases', 'GET')])

    def test_every_http_attempt_reserves_shared_ledger_before_send(self):
        import inspect
        self.assertIn('manifest', inspect.signature(api.Transport).parameters)
        http = api.Transport('fake-key', manifest={'continuation_id': 'case-global-72fa-20261019-1909',
                                                   'http_requests': 0})
        opener = Mock()
        opener.open.side_effect = URLError('offline')
        with patch.object(api, 'save_manifest'), patch.object(api, 'build_opener', return_value=opener):
            with self.assertRaises(URLError):
                http.request('GET', '/cases')
        self.assertEqual(http.manifest['http_requests'], 1)

    def test_http_budget_exhaustion_prevents_send(self):
        import inspect
        self.assertIn('manifest', inspect.signature(api.Transport).parameters)
        http = api.Transport('fake-key', manifest={'continuation_id': 'case-global-72fa-20261019-1909',
                                                   'http_requests': 200})
        opener = Mock()
        with patch.object(api, 'build_opener', return_value=opener), self.assertRaises(ValueError):
            http.request('GET', '/cases')
        opener.open.assert_not_called()

    def method(self, **kwargs):
        return {'httpMethod': kwargs['httpMethod'], 'apiKeyRequired': True, 'authorizationType': 'NONE',
                'methodIntegration': {'type': 'AWS_PROXY', 'httpMethod': 'POST',
                'uri': f'arn:aws:apigateway:{deploy.REGION}:lambda:path/2015-03-31/functions/{deploy.FUNCTION}/invocations'}}

    def method_missing_global(self, **kwargs):
        if kwargs['resourceId'] == '/cases' and kwargs['httpMethod'] == 'GET':
            raise ClientError({'Error': {'Code': 'NotFoundException'}}, 'GetMethod')
        return self.method(**kwargs)

    def gateway(self):
        gateway = Mock()
        gateway.get_paginator.return_value.paginate.return_value = [{'items': [
            {'path': p, 'id': p} for p in ('/clients', '/cases', '/cases/{case_id}', '/clients/{client_id}/cases')]}]
        gateway.get_method.side_effect = self.method
        gateway.get_integration.side_effect = lambda **kw: self.method(**kw)['methodIntegration']
        gateway.get_stage.return_value = {'deploymentId': 'before', 'methodSettings': {'*/*': {'throttlingRateLimit': 2}}}
        return gateway

    def test_route_validation_rejects_missing_post_bad_auth_and_access_denied(self):
        self.assertTrue(callable(getattr(deploy, 'require_routes', None)))
        for broken in ('post', 'auth', 'denied', 'uri'):
            gateway = self.gateway()
            def detail(**kw):
                if kw['resourceId'] == '/cases' and kw['httpMethod'] == 'POST':
                    if broken in ('post', 'denied'):
                        raise ClientError({'Error': {'Code': 'NotFoundException' if broken == 'post' else 'AccessDeniedException'}}, 'GetMethod')
                    value = self.method(**kw)
                    if broken == 'auth':
                        value['apiKeyRequired'] = False
                    else:
                        value['methodIntegration']['uri'] = 'foreign'
                    return value
                return self.method(**kw)
            gateway.get_method.side_effect = detail
            with self.subTest(broken=broken), self.assertRaises((ValueError, ClientError)):
                deploy.require_routes(gateway, deployed=False)

    def test_gateway_additive_publication_and_owned_recovery(self):
        self.assertTrue(callable(getattr(deploy, 'publish_gateway', None)), 'missing guarded publication')
        self.assertTrue(callable(getattr(deploy, 'recover_gateway', None)), 'missing owned recovery')
        gateway = self.gateway()
        gateway.get_method.side_effect = self.method_missing_global
        snapshot = deploy.require_routes(gateway, deployed=False)
        state = {'api': snapshot, 'revision': 'ours'}
        gateway.put_method.side_effect = lambda **kw: setattr(gateway.get_method, 'side_effect', self.method)
        s = Mock()
        s.client.side_effect = lambda name, **kw: gateway if name == 'apigateway' else Mock(
            get_function_configuration=Mock(return_value={'RevisionId': 'ours'}))
        def put(**kw):
            gateway.get_method.side_effect = self.method
        gateway.put_integration.side_effect = put
        gateway.create_deployment.return_value = {'id': 'owned'}
        gateway.create_deployment.side_effect = lambda **kw: (setattr(gateway.get_stage, 'return_value',
            {'deploymentId': 'owned', 'methodSettings': {'*/*': {'throttlingRateLimit': 2}}}) or {'id': 'owned'})
        gateway.update_stage.side_effect = lambda **kw: setattr(gateway.get_stage, 'return_value', snapshot['stage'])
        with patch.object(deploy, 'store_state') as saved:
            deploy.publish_gateway(s, Path('/unused'), state)
            self.assertGreater(saved.call_count, 2)
            gateway.put_method.assert_called_once_with(restApiId=deploy.API, resourceId='/cases',
                httpMethod='GET', authorizationType='NONE', apiKeyRequired=True)
            gateway.put_integration.assert_called_once_with(restApiId=deploy.API, resourceId='/cases',
                httpMethod='GET', type='AWS_PROXY', integrationHttpMethod='POST',
                uri=self.method(httpMethod='POST')['methodIntegration']['uri'])
            gateway.create_deployment.assert_called_once_with(restApiId=deploy.API, stageName='v1')
            deploy.recover_gateway(s, Path('/unused'), state)
        gateway.update_stage.assert_called_once()
        gateway.delete_method.assert_called_once()

    def test_gateway_foreign_stage_stops_before_mutation(self):
        self.assertTrue(callable(getattr(deploy, 'publish_gateway', None)))
        gateway = self.gateway()
        snapshot = deploy.require_routes(gateway, deployed=False)
        gateway.get_stage.return_value = {'deploymentId': 'foreign'}
        s = Mock()
        s.client.return_value = gateway
        with patch.object(deploy, 'store_state'), self.assertRaises(ValueError):
            deploy.publish_gateway(s, Path('/unused'), {'api': snapshot, 'revision': 'ours'})
        gateway.put_method.assert_not_called()
        gateway.create_deployment.assert_not_called()

    def test_gateway_partial_failure_retains_intent_and_refuses_foreign_recovery(self):
        self.assertTrue(callable(getattr(deploy, 'publish_gateway', None)))
        for boundary in ('put_method', 'put_integration', 'create_deployment'):
            gateway = self.gateway()
            gateway.get_method.side_effect = self.method_missing_global
            state = {'api': deploy.require_routes(gateway, deployed=False), 'revision': 'ours'}
            gateway.put_method.side_effect = lambda **kw: setattr(gateway.get_method, 'side_effect', self.method)
            s = Mock()
            s.client.side_effect = lambda name, **kw: gateway if name == 'apigateway' else Mock(
                get_function_configuration=Mock(return_value={'RevisionId': 'ours'}))
            def integrate(**kw):
                gateway.get_method.side_effect = self.method
            gateway.put_integration.side_effect = integrate
            getattr(gateway, boundary).side_effect = RuntimeError('operation failed')
            with patch.object(deploy, 'store_state'), self.subTest(boundary=boundary):
                with self.assertRaises(RuntimeError):
                    deploy.publish_gateway(s, Path('/unused'), state)
                self.assertIn('gateway_intent', state)
                gateway.get_stage.return_value = {'deploymentId': 'foreign'}
                with self.assertRaises(ValueError):
                    deploy.recover_gateway(s, Path('/unused'), state)
            gateway.delete_method.assert_not_called()

    def test_last_http_slot_cannot_be_spent_twice_by_threads(self):
        import inspect
        from concurrent.futures import ThreadPoolExecutor
        self.assertIn('manifest', inspect.signature(api.Transport).parameters)
        m = {'http_requests': 199}
        http = api.Transport('fake-key', manifest=m, sleep=Mock())
        opener = Mock()
        opener.open.side_effect = URLError('offline')
        def request(_):
            try:
                http.request('GET', '/cases')
            except (ValueError, URLError):
                pass
        with patch.object(api, 'save_manifest'), patch.object(api, 'build_opener', return_value=opener), ThreadPoolExecutor(2) as pool:
            list(pool.map(request, range(2)))
        self.assertEqual(m['http_requests'], 200)
        opener.open.assert_called_once()

    def test_post_reservation_is_saved_before_ambiguous_send_and_not_replayed(self):
        import inspect
        self.assertIn('manifest', inspect.signature(api.Transport).parameters)
        m = {'http_requests': 0, 'post_attempts': 0}
        http = api.Transport('fake-key', manifest=m)
        opener = Mock()
        with patch.object(api, 'save_manifest') as saved, patch.object(api, 'build_opener', return_value=opener):
            def send(*a, **kw):
                self.assertEqual((m['http_requests'], m['post_attempts']), (1, 1))
                self.assertTrue(saved.called)
                raise URLError('ambiguous')
            opener.open.side_effect = send
            with self.assertRaises(URLError):
                http.request('POST', '/cases', body={}, label='stable')
            with self.assertRaises(ValueError):
                http.request('POST', '/cases', body={}, label='stable')
        opener.open.assert_called_once()

    def test_http_baseline_does_not_start_mutation_clock(self):
        import inspect
        self.assertIn('manifest', inspect.signature(api.Transport).parameters)
        m = {}
        http = api.Transport('fake-key', manifest=m)
        with patch.object(api, 'save_manifest'), patch.object(api, 'build_opener') as opener:
            opener.return_value.open.side_effect = URLError('offline')
            with self.assertRaises(URLError):
                http.request('GET', '/clients', auth='missing')
        self.assertNotIn('live_started_at', m)

    def test_global_traversal_rejects_missing_duplicate_and_cycles(self):
        self.assertTrue(callable(getattr(api, 'global_matrix', None)), 'missing global HTTP scenarios')
        fs = [{'client_id': 'a', 'status': 'active'}, {'client_id': 'b', 'status': 'active'}]
        cases = [{'case_id': str(i), 'client_id': c, 'status': 'open', 'created_at': 'now', 'metadata': {}}
                 for i, c in enumerate(('a', 'b'))]
        for mode in ('good', 'missing', 'duplicate', 'cycle'):
            http = Mock()
            def request(method, path, query=None, auth='valid', **kw):
                if auth != 'valid':
                    return 403, {}, None
                q = query or {}
                if q.get('limit') in ('0', '101', 'bad') or q.get('next_token') == 'bad!' or (q.get('next_token') in ('foreign', 'global') and
                        (path != '/cases' or q.get('limit') != '1' or q['next_token'] == 'foreign')):
                    return 400, {}, 'dynamodb'
                if path != '/cases':
                    return 200, {'cases': cases[:1], 'clients': [], 'next_token': 'foreign'}, 'dynamodb'
                if q.get('next_token') == 'global':
                    return 200, {'cases': cases[:1] if mode == 'duplicate' else cases[1:] if mode != 'missing' else [],
                                 'next_token': 'global' if mode == 'cycle' else None}, 'dynamodb'
                return 200, {'cases': cases[:1], 'next_token': 'global'}, 'dynamodb'
            http.request.side_effect = request
            m = {'scenarios': {}, 'fixtures': fs, 'fixture_cases': cases}
            with patch.object(api, 'save_manifest'), self.subTest(mode=mode):
                if mode == 'good':
                    api.global_matrix(http, m, cases)
                    self.assertIn('global-pagination-and-tokens', m['scenarios'])
                else:
                    with self.assertRaises((AssertionError, ValueError)):
                        api.global_matrix(http, m, cases)

    def test_fixture_inventory_includes_preexisting_cases_for_both_clients(self):
        self.assertTrue(callable(getattr(api, 'fixture_inventory', None)), 'missing complete reused-fixture inventory')
        m = {'fixtures': [{'client_id': 'a', 'status': 'active'}, {'client_id': 'b', 'status': 'active'}],
             'fixture_case_ids': ['old-a'], 'case_ids': ['new-b']}
        with patch.object(api, 'case_partition', side_effect=[['old-a'], ['old-b', 'new-b']]), \
                patch.object(api, 'save_manifest'):
            inventory = api.fixture_inventory(Mock(), m)
        self.assertEqual(inventory, {'a': ['old-a'], 'b': ['old-b', 'new-b']})
        self.assertIn('old-b', m['fixture_inventory']['b'])

    def test_read_only_continuation_requires_bound_successful_prior_evidence(self):
        self.assertTrue(callable(getattr(api, 'continue_read_only', None)), 'missing bounded read-only continuation')
        http = Mock()
        for broken in ({}, {'suite_binding': {'code': 'foreign'}, 'scenarios': {'auth': 'PASS'}}):
            with self.assertRaises(ValueError):
                api.continue_read_only(Mock(), http, broken, {'CodeSha256': 'ours'}, 'deployment')
        http.request.assert_not_called()

    def test_busy_execution_lock_cannot_write_another_invocations_ledger(self):
        import io
        for module, argv in ((deploy, ['tool', 'preflight']), (api, ['tool', '--baseline'])):
            with self.subTest(module=module.__name__), \
                    patch.object(module, 'exclusive_run', side_effect=BlockingIOError('busy')), \
                    patch.object(module, 'save_manifest') as saved, \
                    patch.object(module, 'load_manifest', return_value={}), \
                    patch.object(sys, 'argv', argv), patch('sys.stdout', io.StringIO()):
                self.assertEqual(module.main(), 1)
                saved.assert_not_called()

    def test_preexisting_get_fingerprint_drift_prevents_publication(self):
        gateway = self.gateway()
        state = {'api': deploy.require_routes(gateway, deployed=True)}
        def changed(**kw):
            value = self.method(**kw)
            if kw['resourceId'] == '/cases' and kw['httpMethod'] == 'GET':
                value['requestParameters'] = {'method.request.header.Foreign': True}
            return value
        gateway.get_method.side_effect = changed
        with self.assertRaises(ValueError):
            deploy.guard_gateway(gateway, state)
