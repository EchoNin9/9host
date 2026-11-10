"""
Shared pytest fixtures for 9host API test suite.
Ensures zero AWS network calls by mocking environment variables and AWS services via moto.
"""
import os
import pytest
import boto3
from moto import mock_aws

TABLE_NAME = "9host-main"

@pytest.fixture(autouse=True)
def aws_env(monkeypatch):
    """Set dummy AWS environment variables for all tests."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SECURITY_TOKEN", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("DYNAMODB_TABLE", TABLE_NAME)
    monkeypatch.setenv("TABLE_NAME", TABLE_NAME)
    monkeypatch.setenv("USER_POOL_ID", "us-east-1_dummy")
    monkeypatch.setenv("JWT_SECRET_ARN", "arn:aws:secretsmanager:us-east-1:123456789012:secret:9host-jwt-test")
    monkeypatch.setenv("STRIPE_SECRET_ARN", "arn:aws:secretsmanager:us-east-1:123456789012:secret:9host-stripe-test")
    monkeypatch.setenv("DOMAINS", "echo9.net")
    monkeypatch.setenv("CLOUDFRONT_SITES_DOMAIN", "sites.echo9.net")
    monkeypatch.setenv("CLOUDFRONT_MEDIA_URL", "/media/")
    monkeypatch.setenv("CLOUDFRONT_SITES_DISTRIBUTION_ID", "EDUMMY123")


@pytest.fixture
def dynamodb_table(aws_env):
    """
    Moto-backed DynamoDB fixture creating the 9host-main single table
    with GSIs matching infra/dynamodb.tf:
      - byUser (gsi1pk, gsi1sk)
      - byDomain (gsi2pk, gsi2sk)
      - byEntity (gsi3pk, gsi3sk)
      - bySiteSlug (gsi4pk, gsi4sk)
    """
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = dynamodb.create_table(
            TableName=TABLE_NAME,
            KeySchema=[
                {"AttributeName": "pk", "KeyType": "HASH"},
                {"AttributeName": "sk", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "pk", "AttributeType": "S"},
                {"AttributeName": "sk", "AttributeType": "S"},
                {"AttributeName": "gsi1pk", "AttributeType": "S"},
                {"AttributeName": "gsi1sk", "AttributeType": "S"},
                {"AttributeName": "gsi2pk", "AttributeType": "S"},
                {"AttributeName": "gsi2sk", "AttributeType": "S"},
                {"AttributeName": "gsi3pk", "AttributeType": "S"},
                {"AttributeName": "gsi3sk", "AttributeType": "S"},
                {"AttributeName": "gsi4pk", "AttributeType": "S"},
                {"AttributeName": "gsi4sk", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "byUser",
                    "KeySchema": [
                        {"AttributeName": "gsi1pk", "KeyType": "HASH"},
                        {"AttributeName": "gsi1sk", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                },
                {
                    "IndexName": "byDomain",
                    "KeySchema": [
                        {"AttributeName": "gsi2pk", "KeyType": "HASH"},
                        {"AttributeName": "gsi2sk", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                },
                {
                    "IndexName": "byEntity",
                    "KeySchema": [
                        {"AttributeName": "gsi3pk", "KeyType": "HASH"},
                        {"AttributeName": "gsi3sk", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                },
                {
                    "IndexName": "bySiteSlug",
                    "KeySchema": [
                        {"AttributeName": "gsi4pk", "KeyType": "HASH"},
                        {"AttributeName": "gsi4sk", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                },
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        table.meta.client.get_waiter("table_exists").wait(TableName=TABLE_NAME)
        yield table
