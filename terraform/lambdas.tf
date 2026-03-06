# ─────────────────────────────────────────────────────────────
# Shared Lambda package
# Both Lambdas use the same zip, different handlers.
# ─────────────────────────────────────────────────────────────

locals {
  lambda_zip  = "${path.module}/../.build/bot-factory.zip"
  lambda_hash = filebase64sha256("${path.module}/../.build/bot-factory.zip")
}

# ─────────────────────────────────────────────────────────────
# Embedding Lambda — generate_embeddings
# ─────────────────────────────────────────────────────────────

resource "aws_lambda_function" "embedding" {
  function_name = "bot-factory-embed"
  role          = aws_iam_role.lambda_exec.arn
  handler       = "factory.core.generate_embeddings.lambda_handler"
  runtime       = "python3.12"
  timeout       = 300
  memory_size   = 512

  filename         = local.lambda_zip
  source_code_hash = local.lambda_hash

  environment {
    variables = {
      BOT_DATA_BUCKET = aws_s3_bucket.bot_factory.id
      DATA_SOURCE     = "s3"
      APP_ENV         = "production"
    }
  }

  tags = {
    Project = "bot-factory"
  }
}
