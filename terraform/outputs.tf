output "bucket_name" {
  description = "S3 bucket name"
  value       = aws_s3_bucket.bot_factory.id
}

output "rag_table_name" {
  description = "DynamoDB RAG table name"
  value       = aws_dynamodb_table.rag.name
}

output "history_table_name" {
  description = "DynamoDB history table name"
  value       = aws_dynamodb_table.history.name
}

output "logs_table_name" {
  description = "DynamoDB logs table name"
  value       = aws_dynamodb_table.logs.name
}

output "lambda_exec_role_arn" {
  description = "IAM role ARN for Lambda execution"
  value       = aws_iam_role.lambda_exec.arn
}

output "api_url" {
  description = "Main API Function URL (chat, health, UI)"
  value       = aws_lambda_function_url.api.function_url
}

output "streaming_url" {
  description = "Streaming Function URL (SSE)"
  value       = aws_lambda_function_url.streaming.function_url
}
