"""Read-only TEST control-plane acceptance; never reads or writes table items."""
import unittest

import boto3


class ExecutionResourceTest(unittest.TestCase):
    def test_stack_owned_execution_table_is_ready(self):
        session = boto3.Session(profile_name="ai-hackathon", region_name="eu-central-1")
        self.assertEqual(session.client("sts").get_caller_identity()["Account"], "609394381050")
        ddb = session.client("dynamodb")
        try:
            table = ddb.describe_table(TableName="wonderfulkb-trigger-execution")["Table"]
        except ddb.exceptions.ResourceNotFoundException:
            self.fail("Required TEST execution table wonderfulkb-trigger-execution does not exist")
        self.assertEqual(table["TableStatus"], "ACTIVE")
        self.assertEqual(table["KeySchema"], [
            {"AttributeName": "pk", "KeyType": "HASH"},
            {"AttributeName": "sk", "KeyType": "RANGE"},
        ])
        self.assertEqual(sorted(table["AttributeDefinitions"], key=lambda a: a["AttributeName"]), [
            {"AttributeName": "pk", "AttributeType": "S"},
            {"AttributeName": "sk", "AttributeType": "S"},
        ])
        self.assertEqual(table["BillingModeSummary"]["BillingMode"], "PAY_PER_REQUEST")
        backups = ddb.describe_continuous_backups(TableName=table["TableName"])
        self.assertEqual(backups["ContinuousBackupsDescription"]["PointInTimeRecoveryDescription"]
                         ["PointInTimeRecoveryStatus"], "ENABLED")
        cfn = session.client("cloudformation")
        stack = cfn.describe_stacks(StackName="wonderfulkb-trigger")["Stacks"][0]
        self.assertEqual(stack["StackStatus"], "UPDATE_COMPLETE")
        resource = cfn.describe_stack_resource(StackName=stack["StackId"],
                                               LogicalResourceId="ExecutionTable")["StackResourceDetail"]
        self.assertEqual(resource["PhysicalResourceId"], table["TableName"])
        self.assertEqual(resource["StackId"], stack["StackId"])


if __name__ == "__main__":
    unittest.main()
