# ------------------------------------------------------------------------------
# DynamoDB single-table: 9host-main
# Every item MUST have PK starting with TENANT#. See docs/SCHEMA.md.
# ------------------------------------------------------------------------------

resource "aws_dynamodb_table" "main" {
  name         = "9host-main"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "pk"
  range_key    = "sk"

  attribute {
    name = "pk"
    type = "S"
  }

  attribute {
    name = "sk"
    type = "S"
  }

  # GSI1: byUser — "Which tenants does this user belong to?"
  attribute {
    name = "gsi1pk"
    type = "S"
  }

  attribute {
    name = "gsi1sk"
    type = "S"
  }

  # GSI2: byDomain — "Which tenant/site does this domain map to?"
  attribute {
    name = "gsi2pk"
    type = "S"
  }

  attribute {
    name = "gsi2sk"
    type = "S"
  }

  global_secondary_index {
    name            = "byUser"
    hash_key        = "gsi1pk"
    range_key       = "gsi1sk"
    projection_type = "ALL"
  }

  global_secondary_index {
    name            = "byDomain"
    hash_key        = "gsi2pk"
    range_key       = "gsi2sk"
    projection_type = "ALL"
  }

  tags = {
    Name = "9host-main"
  }
}
