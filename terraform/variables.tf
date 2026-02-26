variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Prefix used for all resource names"
  type        = string
  default     = "bot-factory"
}

variable "environment" {
  description = "Environment label (e.g. dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "lambda_zip_path" {
  description = "Path to the FastAPI Lambda zip artifact"
  type        = string
  default     = "builds/fastapi-app.zip"
}

variable "manage_cloudfront" {
  description = "Whether to create a CloudFront distribution for frontend assets"
  type        = bool
  default     = false
}

variable "bedrock_model_id" {
  description = "Claude model ID used by the API"
  type        = string
  default     = "us.anthropic.claude-sonnet-4-20250514-v1:0"
}

variable "lambda_handler" {
  description = "Lambda handler entrypoint"
  type        = string
  default     = "main.handler"
}
