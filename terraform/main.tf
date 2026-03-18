terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# ─────────────────────────────────────────────────────────────
# S3 — shared bot factory bucket
# ─────────────────────────────────────────────────────────────
resource "aws_s3_bucket" "bot_factory" {
  bucket = var.bucket_name

  tags = {
    Project = "bot-factory"
  }
}

resource "aws_s3_bucket_versioning" "bot_factory" {
  bucket = aws_s3_bucket.bot_factory.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_public_access_block" "bot_factory" {
  bucket = aws_s3_bucket.bot_factory.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# ─────────────────────────────────────────────────────────────
# DynamoDB — RAG embeddings
# ─────────────────────────────────────────────────────────────
resource "aws_dynamodb_table" "rag" {
  name         = var.dynamo_rag_table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "pk"

  attribute {
    name = "pk"
    type = "S"
  }

  attribute {
    name = "bot_id"
    type = "S"
  }

  global_secondary_index {
    name            = "bot_id-index"
    hash_key        = "bot_id"
    projection_type = "ALL"
  }

  tags = {
    Project = "bot-factory"
  }
}

# ─────────────────────────────────────────────────────────────
# DynamoDB — conversation history
# ─────────────────────────────────────────────────────────────
resource "aws_dynamodb_table" "history" {
  name         = var.dynamo_history_table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "session_id"

  attribute {
    name = "session_id"
    type = "S"
  }

  tags = {
    Project = "bot-factory"
  }
}

# ─────────────────────────────────────────────────────────────
# DynamoDB — chat logs
# ─────────────────────────────────────────────────────────────
resource "aws_dynamodb_table" "logs" {
  name         = var.dynamo_logs_table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "id"

  attribute {
    name = "id"
    type = "S"
  }

  tags = {
    Project = "bot-factory"
  }
}

# ─────────────────────────────────────────────────────────────
# DynamoDB — API keys
# ─────────────────────────────────────────────────────────────
resource "aws_dynamodb_table" "api_keys" {
  name         = var.dynamo_api_keys_table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "api_key"

  attribute {
    name = "api_key"
    type = "S"
  }

  tags = {
    Project = "bot-factory"
  }
}

# ─────────────────────────────────────────────────────────────
# IAM — Lambda execution role
# ─────────────────────────────────────────────────────────────
resource "aws_iam_role" "lambda_exec" {
  name = "bot-factory-lambda-exec"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = {
    Project = "bot-factory"
  }
}

resource "aws_iam_role_policy" "lambda_policy" {
  name = "bot-factory-lambda-policy"
  role = aws_iam_role.lambda_exec.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.bot_factory.arn,
          "${aws_s3_bucket.bot_factory.arn}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:Scan",
          "dynamodb:Query",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem"
        ]
        Resource = [
          aws_dynamodb_table.rag.arn,
          "${aws_dynamodb_table.rag.arn}/index/*",
          aws_dynamodb_table.history.arn,
          aws_dynamodb_table.logs.arn,
          aws_dynamodb_table.api_keys.arn
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "lambda:InvokeFunction"
        ]
        Resource = "arn:aws:lambda:*:*:function:bot-factory-self-heal"
      },
      {
        Effect = "Allow"
        Action = [
          "ses:SendEmail"
        ]
        Resource = "*"
      }
    ]
  })
}

# ─────────────────────────────────────────────────────────────
# Outputs
# (Lambdas defined in lambdas.tf)
# ─────────────────────────────────────────────────────────────
output "bucket_name" {
  value       = aws_s3_bucket.bot_factory.id
  description = "Bot Factory S3 bucket name"
}

output "rag_table_name" {
  value       = aws_dynamodb_table.rag.name
  description = "RAG DynamoDB table name"
}

output "lambda_role_arn" {
  value       = aws_iam_role.lambda_exec.arn
  description = "Lambda execution role ARN"
}

output "stream_function_url" {
  value       = aws_lambda_function_url.streaming.function_url
  description = "Streaming Lambda Function URL"
}

output "stream_function_name" {
  value       = aws_lambda_function.streaming.function_name
  description = "Streaming Lambda function name"
}

output "embed_function_name" {
  value       = aws_lambda_function.embedding.function_name
  description = "Embed Lambda function name"
}

output "self_heal_function_name" {
  value       = aws_lambda_function.self_heal.function_name
  description = "Self-heal Lambda function name"
}
