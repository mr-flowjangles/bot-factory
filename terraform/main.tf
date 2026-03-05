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
# bots/{bot_id}/config.yml
# bots/{bot_id}/prompt.yml
# bots/{bot_id}/data/*.yml
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
  name         = var.dynamo_table_name
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
          "dynamodb:UpdateItem"
        ]
        Resource = [
          aws_dynamodb_table.rag.arn,
          aws_dynamodb_table.logs.arn
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream"
        ]
        Resource = "*"
      }
    ]
  })
}
