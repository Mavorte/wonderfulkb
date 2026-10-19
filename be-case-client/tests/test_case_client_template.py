"""Static packaging checks, not evidence of deployed gateway enforcement."""
import json
from pathlib import Path
import unittest
import re


class CaseClientTemplateTests(unittest.TestCase):
    def setUp(self):
        self.template = json.loads((Path(__file__).resolve().parents[1] / 'template.yaml').read_text())
        self.resources = self.template['Resources']

    def resolve(self, value, backend='mock'):
        """Evaluate the template's actual conditions/refs for both backend branches."""
        params = {k: v['Default'] for k, v in self.template['Parameters'].items()}
        params.update({'DataBackend': backend, 'AWS::Partition': 'aws',
                       'AWS::Region': 'eu-central-1', 'AWS::AccountId': '123456789012',
                       'AWS::StackName': 'offline'})
        def evaluate(v):
            if isinstance(v, list):
                return [r for item in v if (r := evaluate(item)) is not None]
            if not isinstance(v, dict):
                return v
            if 'Ref' in v:
                return None if v['Ref'] == 'AWS::NoValue' else params.get(v['Ref'], v)
            if 'Fn::Equals' in v:
                a, b = v['Fn::Equals']
                return evaluate(a) == evaluate(b)
            if 'Fn::If' in v:
                condition, yes, no = v['Fn::If']
                return evaluate(yes if evaluate(self.template['Conditions'][condition]) else no)
            if 'Fn::Sub' in v:
                return re.sub(r'\$\{([^}]+)\}', lambda m: params[m[1]], v['Fn::Sub'])
            return {k: evaluate(item) for k, item in v.items()}
        return evaluate(value)

    def test_minimal_resource_set_and_tags(self):
        allowed = {'AWS::Serverless::Function', 'AWS::Serverless::Api',
                   'AWS::IAM::Role', 'AWS::Logs::LogGroup', 'AWS::ApiGateway::ApiKey',
                   'AWS::ApiGateway::UsagePlan', 'AWS::ApiGateway::UsagePlanKey'}
        self.assertEqual({r['Type'] for r in self.resources.values()}, allowed)
        self.assertEqual(len(self.resources), 7)
        for resource in self.resources.values():
            if resource['Type'] == 'AWS::ApiGateway::UsagePlanKey':
                continue
            tags = resource['Properties']['Tags']
            if isinstance(tags, list):
                tags = {tag['Key']: tag['Value'] for tag in tags}
            self.assertEqual(tags['project'], 'wonderfulkb')

    def test_function_and_exact_protected_rest_routes(self):
        function = self.resources['CaseClientFunction']['Properties']
        self.assertEqual(function['Runtime'], 'python3.13')
        self.assertEqual(function['CodeUri'], 'src/')
        self.assertEqual(function['Handler'], 'case_client_handler.lambda_handler')
        self.assertEqual(function['MemorySize'], 256)
        self.assertEqual(function['Timeout'], 10)
        env = function['Environment']['Variables']
        for backend in ('mock', 'dynamodb'):
            self.assertEqual(self.resolve(env, backend), {
                'DATA_BACKEND': backend, 'ALLOW_EPHEMERAL_MOCK': 'true' if backend == 'mock' else 'false',
                'CLIENTS_TABLE_NAME': 'wonderfulkb-uw-clients', 'CASES_TABLE_NAME': 'wonderfulkb-uw-cases',
                'CLIENTS_ICO_INDEX_NAME': 'ico-index', 'CASES_CLIENT_CREATED_INDEX_NAME': 'client-created-index'})
        self.assertNotIn('AWS_REGION', env)
        self.assertEqual(self.template['Parameters']['DataBackend']['Default'], 'mock')
        self.assertEqual(function['Role'], {'Fn::GetAtt': ['CaseClientRole', 'Arn']})
        self.assertNotIn('VpcConfig', function)
        self.assertNotIn('ProvisionedConcurrencyConfig', function)
        api = self.resources['CaseClientApi']['Properties']
        self.assertEqual(api['StageName'], 'v1')
        self.assertTrue(api['Auth']['ApiKeyRequired'])
        routes = set()
        for event in function['Events'].values():
            self.assertEqual(event['Type'], 'Api')
            properties = event['Properties']
            self.assertEqual(properties['RestApiId'], {'Ref': 'CaseClientApi'})
            self.assertNotEqual(properties.get('Auth', {}).get('ApiKeyRequired'), False)
            routes.add((properties['Method'].upper(), properties['Path']))
        self.assertEqual(len(function['Events']), 5)
        self.assertEqual(routes, {('GET', '/clients'), ('POST', '/cases'),
                                  ('GET', '/cases'), ('GET', '/cases/{case_id}'),
                                  ('GET', '/clients/{client_id}/cases')})

    def test_key_stage_binding_and_json_gateway_errors(self):
        plan = self.resources['CaseClientUsagePlan']['Properties']
        self.assertEqual(plan['ApiStages'], [{'ApiId': {'Ref': 'CaseClientApi'},
                                             'Stage': {'Ref': 'CaseClientApiv1Stage'}}])
        self.assertEqual(self.resources['CaseClientUsagePlanKey']['Properties'], {
            'KeyId': {'Ref': 'CaseClientApiKey'}, 'KeyType': 'API_KEY',
            'UsagePlanId': {'Ref': 'CaseClientUsagePlan'}})
        self.assertTrue(self.resources['CaseClientApiKey']['Properties']['Enabled'])
        responses = self.resources['CaseClientApi']['Properties']['GatewayResponses']
        for kind, status in [('INVALID_API_KEY', '403'), ('ACCESS_DENIED', '403'),
                             ('DEFAULT_4XX', '403'), ('THROTTLED', '429'), ('QUOTA_EXCEEDED', '429')]:
            self.assertEqual(responses[kind]['StatusCode'], status)
            error = json.loads(responses[kind]['ResponseTemplates']['application/json'])
            self.assertEqual(set(error), {'error'})

    def test_only_scoped_log_permissions_and_nonsecret_outputs(self):
        role = self.resources['CaseClientRole']['Properties']
        self.assertNotIn('ManagedPolicyArns', role)
        self.assertEqual(role['AssumeRolePolicyDocument']['Statement'], [{
            'Effect': 'Allow', 'Principal': {'Service': 'lambda.amazonaws.com'},
            'Action': 'sts:AssumeRole'}])
        statements = [statement for policy in self.resolve(role['Policies'])
                      for statement in policy['PolicyDocument']['Statement']]
        self.assertEqual(len(statements), 1)
        self.assertEqual(set(statements[0]['Action']), {'logs:CreateLogStream', 'logs:PutLogEvents'})
        self.assertEqual(statements[0]['Effect'], 'Allow')
        self.assertEqual(statements[0]['Resource'],
            'arn:aws:logs:eu-central-1:123456789012:log-group:/aws/lambda/offline-case-client:log-stream:*')
        self.assertEqual(self.resources['CaseClientLogGroup']['Properties']['RetentionInDays'], 7)
        self.assertEqual(set(self.template['Outputs']),
                         {'ApiUrl', 'FunctionName', 'RestApiId', 'ApiKeyId', 'UsagePlanId'})
        self.assertEqual(self.template['Outputs']['ApiKeyId']['Value'], {'Ref': 'CaseClientApiKey'})

    def test_exact_external_database_permissions_only_when_enabled(self):
        role = self.resources['CaseClientRole']['Properties']
        prefix = 'arn:aws:dynamodb:eu-central-1:609394381050:table/'
        expected = {
            prefix + 'wonderfulkb-uw-clients': {'dynamodb:GetItem', 'dynamodb:Scan', 'dynamodb:ConditionCheckItem'},
            prefix + 'wonderfulkb-uw-clients/index/ico-index': {'dynamodb:Query'},
            prefix + 'wonderfulkb-uw-cases': {'dynamodb:GetItem', 'dynamodb:PutItem'},
            prefix + 'wonderfulkb-uw-cases/index/client-created-index': {'dynamodb:Query'}}
        for backend in ('mock', 'dynamodb'):
            statements = [s for p in self.resolve(role['Policies'], backend)
                          for s in p['PolicyDocument']['Statement']]
            actual = {}
            for statement in statements:
                self.assertEqual(statement['Effect'], 'Allow')
                for action in statement['Action']:
                    if action.startswith('dynamodb:'):
                        actual.setdefault(statement['Resource'], set()).add(action)
            self.assertEqual(actual, expected if backend == 'dynamodb' else {})


if __name__ == '__main__':
    unittest.main()
