output "frontend_bucket_name" {
  value       = aws_s3_bucket.frontend.bucket
  description = "S3 bucket serving frontend files"
}

output "data_bucket_name" {
  value       = aws_s3_bucket.bot_data.bucket
  description = "S3 bucket storing bot prompts and data"
}

output "lambda_function_name" {
  value       = aws_lambda_function.api.function_name
  description = "Lambda function hosting the API"
}

output "cloudfront_domain_name" {
  value       = try(aws_cloudfront_distribution.frontend[0].domain_name, null)
  description = "CloudFront domain for frontend bucket (if enabled)"
}
