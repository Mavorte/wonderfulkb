from pathlib import Path

import yaml


class Loader(yaml.SafeLoader):
    pass


Loader.add_multi_constructor("!", lambda loader, suffix, node: loader.construct_scalar(node) if isinstance(node, yaml.ScalarNode) else None)


def test_table_matches_contract():
    template = yaml.load((Path(__file__).parents[1] / "analysis-table.yaml").read_text(), Loader)
    table = next(r for r in template["Resources"].values() if r["Type"] == "AWS::DynamoDB::Table")["Properties"]
    assert table["TableName"] == "wonderfulkb-uw-document-analysis" and table["BillingMode"] == "PAY_PER_REQUEST"
    assert [(k["AttributeName"], k["KeyType"]) for k in table["KeySchema"]] == [("case_id", "HASH"), ("document_id", "RANGE")]
    assert {a["AttributeType"] for a in table["AttributeDefinitions"]} == {"S"}
    assert {"Key": "project", "Value": "wonderfulkb"} in table["Tags"]
    assert set(template["Resources"]) == {"DocumentAnalysisTable"}  # nothing but the table
