# ─────────────────────────────────────────────────────────────
# API Keys table (add to main.tf alongside existing DynamoDB tables)
# ─────────────────────────────────────────────────────────────

resource "aws_dynamodb_table" "api_keys" {
  name         = "BotFactoryApiKeys"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "pk"

  attribute {
    name = "pk"
    type = "S"
  }

  tags = {
    Project = "bot-factory"
  }
}

# Add this to the streaming Lambda environment variables block:
#   API_KEYS_TABLE = aws_dynamodb_table.api_keys.name
#
# And add this output:

output "api_keys_table_name" {
  value       = aws_dynamodb_table.api_keys.name
  description = "API Keys DynamoDB table name"
}
