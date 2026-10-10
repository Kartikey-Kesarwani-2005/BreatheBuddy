# Deploy to AWS (SAM)

This deploys the **Ship It** half of BreatheBuddy: the 15-minute pipeline on
Lambda + Step Functions, the API on API Gateway, alerts on SNS, state on S3 +
DynamoDB, auth on Cognito, and the dashboard on CloudFront + S3. Everything is in
[`infra/template.yaml`](../infra/template.yaml); there is no manual console setup.

> The local demo (`python run.py`) needs none of this. Deploy only if you want the
> cloud version, or to show "Built on AWS" for judging.

---

## 1. Prerequisites

| Tool | Why | Check |
|------|-----|-------|
| AWS account with credentials | to create resources | `aws sts get-caller-identity` |
| AWS CLI v2 | credentials + a few post-deploy commands | `aws --version` |
| AWS SAM CLI | build + deploy the template | `sam --version` |
| Python 3.12 | SAM packages the Lambda with this runtime | `python --version` |

Recommended region: **`ap-south-1`** (the template and `samconfig.toml` default to it).

```bash
aws configure            # or: aws sso login --profile <name>
```

## 2. Build and deploy

```bash
sam build  -t infra/template.yaml
sam deploy -t infra/template.yaml --guided
```

The first run asks for a stack name and an artifact S3 bucket; `infra/samconfig.toml`
already sets sensible defaults (`stack_name = breathebuddy`, `resolve_s3 = true`,
`region = ap-south-1`, `capabilities = CAPABILITY_IAM`), so after the first guided run
you can just use:

```bash
sam deploy -t infra/template.yaml
```

### Parameters you can pass

| Parameter | Default | Meaning |
|-----------|---------|---------|
| `Stage` | `prod` | API Gateway stage name |
| `AlertEmail` | *(blank)* | If set, an email address subscribed to the SNS topic |
| `City` | `Delhi` | City name shown by the API |
| `RequireAuth` | `false` | If `true`, `/subscribe` and `/cycle` require a Cognito token |
| `SagemakerEndpoint` | *(blank)* | Optional deployed endpoint for the nowcast model |
| `DomainName` / `HostedZoneId` / `CertificateArn` | *(blank)* | Optional custom domain on CloudFront |

Example with email alerts:

```bash
sam deploy -t infra/template.yaml --parameter-overrides AlertEmail=you@example.com
```

### Lean package tip

The Lambda runtime in Python 3.12 already ships `boto3`, and the optional packages
in the root `requirements.txt` (`strands-agents`, `cedarpy`, ...) are only needed for
the local agent/Cedar path. If `sam build` feels slow or the package is large, build
once with a minimal requirements file:

```bash
mv requirements.txt requirements-full.txt
printf 'boto3\n' > requirements.txt
sam build -t infra/template.yaml
mv requirements-full.txt requirements.txt
```

The deployed pipeline still runs (it falls back to the built-in Cedar evaluator and
the deterministic agent exactly like the offline demo).

## 3. What gets created

| Layer | Resources |
|-------|-----------|
| Data | S3 raw bucket, 3 DynamoDB tables (readings, alerts, subscribers) |
| Pipeline | Lambda `lambda_ingest` / `lambda_nowcast` / `lambda_policy` / `lambda_alert` / `lambda_buffer` |
| Orchestration | Step Functions state machine `breathebuddy-pipeline` |
| Schedule | EventBridge rule firing `lambda_ingest` every 15 minutes |
| Messaging | SNS topic (+ optional email sub), SQS buffer queue |
| API | API Gateway REST API -> `lambda_api` (proxy) |
| Auth | Cognito user pool + web client |
| Hosting | S3 site bucket + CloudFront distribution (+ Route 53 if a domain is set) |
| Observability | CloudWatch log groups, an API error alarm, and a `breathebuddy` dashboard |

## 4. After deploy

Grab the outputs (the deploy prints them, or use `sam list stack-outputs --stack-name breathebuddy`):

- `ApiUrl` - the API Gateway endpoint
- `StateMachineArn` - the pipeline state machine
- `SiteBucketName` - the S3 bucket for the dashboard
- `SiteUrl` - the CloudFront URL
- `UserPoolId`, `UserPoolClientId` - for the sign-in button

**a. Run the pipeline once** (EventBridge also runs it every 15 minutes):

```bash
aws stepfunctions start-execution \
  --state-machine-arn <StateMachineArn> \
  --region ap-south-1
```

**b. Host the dashboard.** Sync the static frontend and invalidate CloudFront:

```bash
aws s3 sync frontend/ s3://<SiteBucketName>/ --exclude "*.map"
aws cloudfront create-invalidation --distribution-id <dist-id> --paths "/*"
```

**c. Point the dashboard at the API.** Edit `frontend/amplify-config.js` and set
`apiBase` to `<ApiUrl>`, then re-sync:

```js
window.BB_CONFIG = { apiBase: "https://<id>.execute-api.ap-south-1.amazonaws.com/prod", cognito: null };
```

(Alternatively, connect the repo in **AWS Amplify Hosting** - `amplify.yml` at the
repo root is already configured to publish `frontend/`.)

**d. Optional - password sign-in.** `RequireAuth` is `false` by default so the demo
works without a login. To turn on the gate, create a user and redeploy with
`RequireAuth=true`:

```bash
aws cognito-idp admin-create-user --user-pool-id <UserPoolId> --username you@example.com
sam deploy -t infra/template.yaml --parameter-overrides RequireAuth=true
```

## 5. Verify the deployment

```bash
curl https://<id>.execute-api.ap-south-1.amazonaws.com/prod/health
curl "https://<id>.execute-api.ap-south-1.amazonaws.com/prod/aqi?lat=28.61&lon=77.19"
curl https://<id>.execute-api.ap-south-1.amazonaws.com/prod/openapi.json
```

Open `<SiteUrl>` for the dashboard.

## 6. Tear it down

```bash
# empty the two buckets first (CloudFormation won't delete non-empty buckets)
aws s3 rm s3://<SiteBucketName> --recursive
aws s3 rm s3://<RawBucket> --recursive
sam delete --stack-name breathebuddy
```

---

## Prefer to try AWS locally? (LocalStack)

No AWS account needed, uses the same `breathebuddy` package:

```bash
docker compose -f infra/localstack/docker-compose.yml up -d
pip install boto3
python scripts/localstack_bootstrap.py     # prints the BB_* env vars to export
# export the printed vars, then:
BB_USE_AWS=true python scripts/localstack_cycle.py
```

See [`scripts/localstack_cycle.py`](../scripts/localstack_cycle.py) for the full path.
