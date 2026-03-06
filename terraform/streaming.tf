# ─────────────────────────────────────────────────────────────
# Streaming Lambda — Function URL with RESPONSE_STREAM
# Bypasses API Gateway for real token-by-token SSE delivery.
# Reuses the same IAM role as the Chalice Lambda.
# ─────────────────────────────────────────────────────────────

resource "aws_lambda_function" "streaming" {
  function_name = "bot-factory-streaming"
  role          = aws_iam_role.lambda_exec.arn
  handler       = "factory.streaming_handler.handler"
  runtime       = "python3.12"
  timeout       = 120
  memory_size   = 512

  filename         = "${path.module}/../.build/streaming.zip"
  source_code_hash = filebase64sha256("${path.module}/../.build/streaming.zip")

  environment {
    variables = {
      BOT_DATA_BUCKET = aws_s3_bucket.bot_factory.id
      APP_ENV         = "production"
    }
  }

  tags = {
    Project = "bot-factory"
  }
}

resource "aws_lambda_function_url" "streaming" {
  function_name      = aws_lambda_function.streaming.function_name
  authorization_type = "NONE"
  invoke_mode        = "RESPONSE_STREAM"

  cors {
    allow_origins  = ["*"]
    allow_methods  = ["POST"]
    allow_headers  = ["content-type"]
    expose_headers = ["*"]
    max_age        = 3600
  }
}

output "streaming_url" {
  description = "Function URL for streaming chat endpoint"
  value       = aws_lambda_function_url.streaming.function_url
}
