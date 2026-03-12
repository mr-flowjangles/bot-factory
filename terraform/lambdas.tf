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
      BOT_DATA_BUCKET        = aws_s3_bucket.bot_factory.id
      RAG_TABLE_NAME         = aws_dynamodb_table.rag.name
      LOGS_TABLE_NAME        = aws_dynamodb_table.logs.name
      RAG_BOT_ID_INDEX_NAME  = "bot_id-index"
      APP_ENV                = "production"
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
# Streaming Lambda — Lambda Web Adapter + Flask (dev_server.py)
# SSE token-by-token via Function URL
# ─────────────────────────────────────────────────────────────

resource "aws_lambda_function" "streaming" {
  function_name = "bot-factory-stream"
  role          = aws_iam_role.lambda_exec.arn
  handler       = "run.sh"
  runtime       = "python3.12"
  timeout       = 120
  memory_size   = 1024

  filename         = local.lambda_zip
  source_code_hash = local.lambda_hash

  layers = [
    "arn:aws:lambda:us-east-1:753240598075:layer:LambdaAdapterLayerX86:24"
  ]

  environment {
    variables = {
      BOT_DATA_BUCKET         = aws_s3_bucket.bot_factory.id
      RAG_TABLE_NAME          = aws_dynamodb_table.rag.name
      LOGS_TABLE_NAME         = aws_dynamodb_table.logs.name
      RAG_BOT_ID_INDEX_NAME   = "bot_id-index"
      APP_ENV                 = "production"
      AWS_LWA_INVOKE_MODE     = "response_stream"
      AWS_LWA_PORT            = "8080"
      AWS_LAMBDA_EXEC_WRAPPER = "/opt/bootstrap"
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
      BOT_DATA_BUCKET        = aws_s3_bucket.bot_factory.id
      RAG_TABLE_NAME         = aws_dynamodb_table.rag.name
      RAG_BOT_ID_INDEX_NAME  = "bot_id-index"
      DATA_SOURCE            = "s3"
      APP_ENV                = "production"
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

resource "aws_lambda_permission" "api_public_invoke" {
  statement_id  = "AllowPublicInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api.function_name
  principal     = "*"
}

resource "aws_lambda_permission" "streaming_public_invoke" {
  statement_id  = "AllowPublicInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.streaming.function_name
  principal     = "*"
}
