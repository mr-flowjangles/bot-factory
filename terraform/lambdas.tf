# ─────────────────────────────────────────────────────────────
# Shared Lambda package
# All Lambdas use the same zip, different handlers.
# ─────────────────────────────────────────────────────────────

locals {
  lambda_zip  = "${path.module}/../.build/bot-factory.zip"
  lambda_hash = filebase64sha256("${path.module}/../.build/bot-factory.zip")
}

# ─────────────────────────────────────────────────────────────
# Main API Lambda — handler.handler
# Serves /chat, /health, chat.html
# ─────────────────────────────────────────────────────────────

resource "aws_lambda_function" "api" {
  function_name = "bot-factory-api"
  role          = aws_iam_role.lambda_exec.arn
  handler       = "handler.handler"
  runtime       = "python3.12"
  timeout       = 30
  memory_size   = 1024

  filename         = local.lambda_zip
  source_code_hash = local.lambda_hash

  environment {
    variables = {
      BOT_DATA_BUCKET = aws_s3_bucket.bot_factory.id
      APP_ENV         = "production"
    }
  }

  tags = { Project = "bot-factory" }
}

resource "aws_lambda_function_url" "api" {
  function_name      = aws_lambda_function.api.function_name
  authorization_type = "NONE"
  invoke_mode        = "BUFFERED"

  cors {
    allow_origins  = ["*"]
    allow_methods  = ["*"]
    allow_headers  = ["content-type"]
    expose_headers = ["*"]
    max_age        = 3600
  }
}

# ─────────────────────────────────────────────────────────────
# Streaming Lambda — streaming_handler.handler
# SSE token-by-token via Function URL
# ─────────────────────────────────────────────────────────────

resource "aws_lambda_function" "streaming" {
  function_name = "bot-factory-stream"
  role          = aws_iam_role.lambda_exec.arn
  handler       = "factory.streaming_handler.handler"
  runtime       = "python3.12"
  timeout       = 120
  memory_size   = 1024

  filename         = local.lambda_zip
  source_code_hash = local.lambda_hash

  environment {
    variables = {
      BOT_DATA_BUCKET = aws_s3_bucket.bot_factory.id
      APP_ENV         = "production"
    }
  }

  tags = { Project = "bot-factory" }
}

resource "aws_lambda_function_url" "streaming" {
  function_name      = aws_lambda_function.streaming.function_name
  authorization_type = "NONE"
  invoke_mode        = "RESPONSE_STREAM"

  cors {
    allow_origins  = ["*"]
    allow_methods  = ["*"]
    allow_headers  = ["content-type"]
    expose_headers = ["*"]
    max_age        = 3600
  }
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

  tags = { Project = "bot-factory" }
}

# ─────────────────────────────────────────────────────────────
# Public invoke permissions for Function URLs
# ─────────────────────────────────────────────────────────────

resource "aws_lambda_permission" "api_public" {
  statement_id           = "AllowPublicAccess"
  action                 = "lambda:InvokeFunctionUrl"
  function_name          = aws_lambda_function.api.function_name
  principal              = "*"
  function_url_auth_type = "NONE"
}

resource "aws_lambda_permission" "streaming_public" {
  statement_id           = "AllowPublicAccess"
  action                 = "lambda:InvokeFunctionUrl"
  function_name          = aws_lambda_function.streaming.function_name
  principal              = "*"
  function_url_auth_type = "NONE"
}
