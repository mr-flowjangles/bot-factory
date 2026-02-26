# Bot Factory: Infra & Migration Gaps

This is a quick audit based on the current repository state for "first run" readiness and Terraform migration.

## What stands out immediately

1. **No Terraform code existed yet**
   - Deployment is currently manual/CLI based from README commands.
   - No stateful definition for Lambda, DynamoDB, S3, IAM, CloudFront.

2. **Table mismatch risk**
   - `scripts/init-dynamodb.sh` creates `ChatbotRAG` and `ChatHistory`.
   - Runtime logging in `factory/core/router.py` writes to `ChatbotLogs`.
   - If only init script runs, logging table is missing in local/AWS.

3. **API key/provider drift in docs vs code**
   - Root `README.md` still describes OpenAI + Anthropic key flow.
   - Core runtime code primarily calls Bedrock (`bedrock-runtime`) for embedding + Claude.
   - This can cause onboarding confusion and incorrect env setup.

4. **Packaging path drift in Dockerfile**
   - `docker/api.Dockerfile` copies `core/` and `bots/` from repo root.
   - Actual source is under `factory/core` and `factory/bots`.
   - Local dev works via bind mount, but image-only build/deploy can break.

## Terraform layer added in this commit

A bootstrap Terraform layer now exists under `terraform/` and manages:

- DynamoDB: `ChatbotRAG`, `ChatHistory`, `ChatbotLogs`
- S3: frontend bucket + bot data bucket
- IAM: Lambda execution role + data/Bedrock permissions
- Lambda: API function wiring with environment variables
- Optional CloudFront distribution

## Still missing for a production-grade Terraform rollout

1. **API front door**
   - API Gateway HTTP API or Lambda Function URL + auth/CORS strategy.

2. **Frontend hardening**
   - CloudFront Origin Access Control + private S3 bucket policy.
   - Custom domain + ACM certificate + Route53 records.

3. **Artifact pipeline**
   - Deterministic Lambda packaging (build step, artifact hash, promotion flow).

4. **Secret strategy**
   - Store secrets in SSM Parameter Store or Secrets Manager.
   - Inject into Lambda via Terraform-managed references.

5. **Environment separation**
   - Separate state/workspaces/accounts for dev/staging/prod.
   - Optionally environment-prefixed DynamoDB names to avoid collisions.

6. **Observability/ops**
   - Structured log retention, CloudWatch alarms, dashboards, and budget alarms.

