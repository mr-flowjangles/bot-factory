output "bucket_name" {
  description = "S3 bucket name — set this as S3_BUCKET in your .env"
  value       = aws_s3_bucket.bot_factory.id
}

output "rag_table_name" {
  description = "DynamoDB RAG table name"
  value       = aws_dynamodb_table.rag.name
}

output "logs_table_name" {
  description = "DynamoDB logs table name"
  value       = aws_dynamodb_table.logs.name
}

output "lambda_exec_role_arn" {
  description = "IAM role ARN — Chalice will use this for Lambda"
  value       = aws_iam_role.lambda_exec.arn
}
