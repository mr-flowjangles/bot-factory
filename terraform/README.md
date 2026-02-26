# Terraform Layer (Bootstrap)

This layer captures the minimum AWS resources the current code assumes already exist:

- DynamoDB tables: `ChatbotRAG`, `ChatHistory`, `ChatbotLogs`
- S3 buckets: frontend assets + bot data
- Lambda execution role and policy
- API Lambda function
- Optional CloudFront distribution for frontend

## Quick start

```bash
cd terraform
terraform init
terraform plan -var='environment=prod' -var='lambda_zip_path=builds/fastapi-app.zip'
terraform apply -var='environment=prod' -var='lambda_zip_path=builds/fastapi-app.zip'
```

## Current gaps still to wire

1. API Gateway / Lambda URL integration for the FastAPI Lambda.
2. Frontend bucket policy + CloudFront Origin Access Control.
3. CI/CD packaging/deploy pipeline (`terraform/builds/fastapi-app.zip` lifecycle).
4. Secrets management for API keys if using direct providers.
5. Separate names per environment for DynamoDB tables if you want isolated stacks.

This is an intentionally safe first pass so you can bring infrastructure under source control before adding full production routing and deployment automation.
