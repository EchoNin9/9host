"""
Test to verify moto DynamoDB table fixture from conftest.py.
"""
def test_dynamodb_fixture_creates_table(dynamodb_table):
    assert dynamodb_table.table_name == "9host-main"
    assert dynamodb_table.table_status == "ACTIVE"
    gsi_names = [gsi["IndexName"] for gsi in dynamodb_table.global_secondary_indexes]
    assert "byUser" in gsi_names
    assert "byDomain" in gsi_names
    assert "byEntity" in gsi_names
    assert "bySiteSlug" in gsi_names
