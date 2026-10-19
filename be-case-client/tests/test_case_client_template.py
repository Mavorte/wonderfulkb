"""Static packaging checks, not evidence of deployed gateway enforcement."""
import json
from pathlib import Path
import unittest


class CaseClientTemplateTests(unittest.TestCase):
    def setUp(self):
        self.template = json.loads((Path(__file__).resolve().parents[1] / 'template.yaml').read_text())
        self.resources = self.template['Resources']

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
        self.assertEqual(function['Environment']['Variables'], {
            'DATA_BACKEND': 'mock', 'ALLOW_EPHEMERAL_MOCK': 'true'})
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
        self.assertEqual(len(function['Events']), 4)
        self.assertEqual(routes, {('GET', '/clients'), ('POST', '/cases'),
                                  ('GET', '/cases/{case_id}'), ('GET', '/clients/{client_id}/cases')})

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
        statements = [statement for policy in role['Policies']
                      for statement in policy['PolicyDocument']['Statement']]
        self.assertEqual(len(statements), 1)
        self.assertEqual(set(statements[0]['Action']), {'logs:CreateLogStream', 'logs:PutLogEvents'})
        self.assertEqual(statements[0]['Effect'], 'Allow')
        self.assertEqual(statements[0]['Resource'], {'Fn::Sub':
            'arn:${AWS::Partition}:logs:${AWS::Region}:${AWS::AccountId}:log-group:/aws/lambda/${AWS::StackName}-case-client:log-stream:*'})
        self.assertEqual(self.resources['CaseClientLogGroup']['Properties']['RetentionInDays'], 7)
        self.assertEqual(set(self.template['Outputs']),
                         {'ApiUrl', 'FunctionName', 'RestApiId', 'ApiKeyId', 'UsagePlanId'})
        self.assertEqual(self.template['Outputs']['ApiKeyId']['Value'], {'Ref': 'CaseClientApiKey'})


if __name__ == '__main__':
    unittest.main()
