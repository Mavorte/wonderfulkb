"""Shape of template.yaml: the properties the design depends on (and cfn-lint when it is installed)."""
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

HERE = Path(__file__).resolve().parents[1]


class Loader(yaml.SafeLoader):
    pass


def _tag(loader, suffix, node):
    value = loader.construct_scalar(node) if isinstance(node, yaml.ScalarNode) else (
        loader.construct_sequence(node, deep=True) if isinstance(node, yaml.SequenceNode) else loader.construct_mapping(node, deep=True))
    return {suffix if suffix.startswith("Fn::") or suffix == "Ref" else f"Fn::{suffix}": value}


Loader.add_multi_constructor("!", _tag)


@pytest.fixture(scope="module")
def template():
    return yaml.load((HERE / "template.yaml").read_text(), Loader=Loader)


def resources(template, kind):
    return {name: r for name, r in template["Resources"].items() if r["Type"] == kind}


def test_every_resource_that_can_be_tagged_has_the_project_tag(template):
    for name, r in template["Resources"].items():
        if r["Type"] in ("AWS::SQS::Queue", "AWS::IAM::Role", "AWS::Logs::LogGroup"):
            assert {"Key": "project", "Value": "wonderfulkb"} in r["Properties"]["Tags"], name
        if r["Type"] == "AWS::Serverless::Function":
            assert r["Properties"].get("Tags", {}).get("project", "wonderfulkb") == "wonderfulkb"
    assert template["Globals"]["Function"]["Tags"]["project"] == "wonderfulkb"


def test_names_carry_the_prefix(template):
    for r in template["Resources"].values():
        props = r["Properties"]
        for key in ("FunctionName", "QueueName", "RoleName", "AlarmName", "LogGroupName"):
            if key in props:
                assert "wonderfulkb" in props[key], props[key]


def test_queue_timing_is_consistent(template):
    queue = template["Resources"]["DocumentQueue"]["Properties"]
    worker = template["Resources"]["WorkerFunction"]["Properties"]
    assert worker["Timeout"] == 900
    assert queue["VisibilityTimeout"] > worker["Timeout"]
    assert queue["RedrivePolicy"]["maxReceiveCount"] == 3
    assert queue["RedrivePolicy"]["deadLetterTargetArn"] == {"Fn::GetAtt": "DeadLetterQueue.Arn"}


def test_concurrency_is_limited_by_the_mapping_not_by_reserved_concurrency(template):
    worker = template["Resources"]["WorkerFunction"]["Properties"]
    assert "ReservedConcurrentExecutions" not in worker  # the account has 10 in total: a reservation is refused
    assert worker["Events"]["Documents"]["Properties"]["ScalingConfig"]["MaximumConcurrency"] == {"Ref": "MaxConcurrency"}
    assert worker["Events"]["Documents"]["Properties"]["BatchSize"] == 1
    assert template["Parameters"]["MaxConcurrency"]["Default"] == 2


def test_stream_mapping_takes_inserts_only_and_starts_at_latest(template):
    stream = template["Resources"]["EnqueueFunction"]["Properties"]["Events"]["Documents"]["Properties"]
    assert stream["StartingPosition"] == "LATEST"
    assert stream["FilterCriteria"]["Filters"] == [{"Pattern": '{"eventName": ["INSERT"]}'}]
    assert "ReportBatchItemFailures" in stream["FunctionResponseTypes"]


def test_the_worker_is_an_image_and_the_light_functions_are_zips(template):
    assert template["Resources"]["WorkerFunction"]["Properties"]["PackageType"] == "Image"
    for name in ("EnqueueFunction", "DlqFunction"):
        props = template["Resources"][name]["Properties"]
        assert props["Runtime"] == "python3.14" and "PackageType" not in props


def test_no_wildcard_actions_and_wildcard_resources_only_where_aws_has_no_resource_level_permission(template):
    allowed_star = {"textract:AnalyzeDocument", "dynamodb:ListStreams"}
    for name, role in resources(template, "AWS::IAM::Role").items():
        for policy in role["Properties"]["Policies"]:
            for statement in policy["PolicyDocument"]["Statement"]:
                if isinstance(statement, dict) and "Fn::If" in statement:
                    statement = statement["Fn::If"][1]
                actions = statement["Action"] if isinstance(statement["Action"], list) else [statement["Action"]]
                assert not any(a == "*" or a.endswith(":*") for a in actions), (name, actions)
                resource = statement["Resource"]
                if resource == "*":
                    assert set(actions) <= allowed_star, (name, actions)


def test_worker_masks_signatures_and_may_encrypt_but_never_decrypt_or_overwrite_originals(template):
    worker = template["Resources"]["WorkerFunction"]["Properties"]["Environment"]["Variables"]
    assert worker["PIPELINE_REDACT"] == "1" and "PRIVACY_KMS_KEY_ID" in worker
    statements = [s for p in template["Resources"]["WorkerRole"]["Properties"]["Policies"]
                  for s in p["PolicyDocument"]["Statement"]]
    actions = {a for s in statements for a in (s["Action"] if isinstance(s["Action"], list) else [s["Action"]])}
    assert "kms:GenerateDataKey" in actions and "kms:Decrypt" not in actions and "kms:*" not in actions
    kms = next(s for s in statements if "kms:GenerateDataKey" in s["Action"])
    assert kms["Condition"]["ForAllValues:StringEquals"]["kms:EncryptionContextKeys"] == ["case_id", "document_id", "signature_id"]
    for statement in statements:
        put = statement["Action"] if isinstance(statement["Action"], list) else [statement["Action"]]
        if "s3:PutObject" in put:
            assert not any("/original/" in str(r) for r in statement["Resource"]), "the worker must not write originals"


def test_dlq_has_alarms(template):
    alarms = resources(template, "AWS::CloudWatch::Alarm")
    assert {"DeadLetteredAlarm", "DlqNotEmptyAlarm", "QueueStuckAlarm"} <= set(alarms)
    assert alarms["DeadLetteredAlarm"]["Properties"]["MetricName"] == "DeadLettered"


def test_stream_copy_of_the_table_template_differs_only_by_the_stream():
    original = yaml.safe_load((HERE.parents[1] / "documents-table" / "template.yaml").read_text())
    copy = yaml.load((HERE / "documents-table-with-stream.yaml").read_text(), Loader=Loader)
    table = copy["Resources"]["DocumentsTable"]["Properties"]
    assert table.pop("StreamSpecification") == {"StreamViewType": "NEW_IMAGE"}
    assert copy["Resources"] == original["Resources"]
    assert set(copy["Outputs"]) == {"StreamArn"}


@pytest.mark.skipif(not (HERE / ".venv-lint/bin/cfn-lint").exists() and not shutil.which("cfn-lint"), reason="cfn-lint not installed")
def test_cfn_lint_is_clean():
    exe = HERE / ".venv-lint/bin/cfn-lint"
    exe = str(exe) if exe.exists() else shutil.which("cfn-lint")
    for name in ("template.yaml", "documents-table-with-stream.yaml"):
        done = subprocess.run([exe, name], cwd=HERE, capture_output=True, text=True)
        assert done.returncode == 0, done.stdout + done.stderr
