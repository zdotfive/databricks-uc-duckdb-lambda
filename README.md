# Databricks Unity Catalog → DuckDB → AWS Lambda

Query Databricks Unity Catalog Delta tables from an AWS Lambda function using DuckDB and credential vending — no Spark, no Databricks compute.

> **This repository is the companion code for an ongoing article series on LinkedIn.**
> Links will be added as articles are published (see [Articles](#articles) below).

---

## What this project does

A Python AWS Lambda function that:

1. Reads SSM Parameter Store for the Databricks workspace URL and PAT token
2. Calls the Unity Catalog REST API to obtain temporary S3 credentials (credential vending)
3. Uses DuckDB + the Delta extension to query the table directly from S3
4. Returns the result as JSON — callable via direct Lambda invocation or API Gateway REST

No Databricks cluster is started. No Spark. Just DuckDB reading Parquet files from S3 with short-lived credentials.

---

## Architecture

```
Client
  │
  ├── direct invoke ──► AWS Lambda (eu-central-1)
  │                         │
  └── API Gateway REST ──►  │  uc_reader.handler
       (GET /query)         │
                            ├── SSM Parameter Store   (workspace URL + PAT token)
                            ├── UC REST API           (table metadata + temp S3 creds)
                            └── S3 direct read        (eu-west-1, Delta/Parquet files)
                                  via DuckDB delta_scan()
```

**AWS resources (deployed via CDK):**

| Resource | Detail |
|---|---|
| Lambda function | Python 3.12, x86_64, 1 536 MB, 60 s timeout |
| Lambda layer | duckdb 1.4.4 + pyarrow 20.0.0 + requests |
| SSM Parameter Store | `/uc-reader/databricks-workspace` (String) · `/uc-reader/databricks-token` (SecureString) |
| API Gateway REST | `GET /query` with 0.5 GB cache, 60 s TTL |

---

## Why credential vending (and not DuckDB extensions)?

Three approaches were evaluated before settling on credential vending:

### 1. `unity_catalog` DuckDB extension
```sql
INSTALL unity_catalog;
ATTACH 'my_catalog' AS c (TYPE unity_catalog);
```
Works only with **Unity Catalog OSS** (open source). Databricks managed workspaces require OAuth2, which the extension does not support → 401/403 error.

### 2. `uc_catalog` DuckDB extension
Same limitation — designed for UC OSS, not Databricks managed.

### 3. Iceberg REST Catalog (IRC)
Databricks exposes an IRC endpoint at `/api/2.1/unity-catalog/iceberg-rest`.
`ATTACH` via the DuckDB iceberg extension succeeds, but subsequent queries fail with **HTTP 404** because DuckDB URL-encodes the prefix `catalogs/labs` as `catalogs%2Flabs`, which Databricks rejects.

This is a **known and documented bug**: [duckdb/duckdb-iceberg #684](https://github.com/duckdb/duckdb-iceberg/issues/684), fixed in [PR #687](https://github.com/duckdb/duckdb-iceberg/pull/687) (February 2026, not yet released at the time of writing). A related issue affects Nessie catalogs: [#375](https://github.com/duckdb/duckdb-iceberg/issues/375).

### 4. Credential vending ✅ (current approach)
```
UC REST /tables/{table}                  →  table_id + S3 location
UC REST /temporary-table-credentials     →  short-lived STS credentials
DuckDB delta_scan(s3_url)                →  direct S3 read
```
This works today, is stable, and supports Delta tables natively.

---

## Quick start

### Prerequisites

| Tool | Min version |
|---|---|
| Python | 3.12 |
| Node.js | 20 |
| AWS CDK CLI | 2.1105.0+ |
| Docker / Podman | any |
| AWS CLI | 2.x |

### 1 — SSM parameters (one-time)

```bash
aws ssm put-parameter \
  --name "/uc-reader/databricks-workspace" \
  --value "https://<workspace>.cloud.databricks.com" \
  --type String --profile <your-profile> --region eu-central-1

aws ssm put-parameter \
  --name "/uc-reader/databricks-token" \
  --value "dapi..." \
  --type SecureString --profile <your-profile> --region eu-central-1
```

### 2 — Build the Lambda layer

```bash
cd infra/lambda_layer
./build_layer.sh
```

Produces `infra/lambda_layer/dist/layer.zip` (~62 MB, linux/amd64).

### 3 — Deploy

```bash
cd infra
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

AWS_PROFILE=<your-profile> CDK_DEFAULT_REGION=eu-central-1 cdk bootstrap   # one-time
AWS_PROFILE=<your-profile> CDK_DEFAULT_REGION=eu-central-1 \
  cdk deploy --app ".venv/bin/python app.py" --require-approval never
```

See [DEPLOY.md](DEPLOY.md) for the full step-by-step guide.

---

## Usage

### Direct Lambda invocation

```bash
./invoke.sh --table "catalog.schema.table" --filters "age > 25" --limit 10
```

### API Gateway

```bash
./invoke_api.sh --table "catalog.schema.table" --filters "age > 25" --limit 10
```

### Payload format (direct invocation)

```json
{
  "table":   "catalog.schema.table",
  "filters": "customerID = 2033056",
  "limit":   10
}
```

### Response format

```json
{
  "table":   "catalog.schema.table",
  "rows":    10,
  "columns": ["customerID", "name", "age"],
  "data":    { "customerID": [2033056], "name": ["Alice"], "age": [30] }
}
```

---

## Project structure

```
databricks-uc-duckdb-lambda/
├── uc_reader.py              # Lambda handler — core logic
├── invoke.sh                 # Test script: direct Lambda invocation
├── invoke_api.sh             # Test script: API Gateway invocation
├── local_test.py             # Local test helper
├── requirements.txt          # Local dev dependencies
├── DEPLOY.md                 # Full deployment guide
└── infra/
    ├── app.py                # CDK entry point
    ├── cdk.json
    ├── requirements.txt      # CDK dependencies (aws-cdk-lib)
    ├── stacks/
    │   └── uc_reader_stack.py  # CDK stack definition
    └── lambda_layer/
        ├── build_layer.sh    # Layer build script (Docker)
        └── docker/
            └── Dockerfile
```

---

## Articles

This repository supports an ongoing series of LinkedIn articles.
Links will be added as each article is published.

| # | Title | Link |
|---|---|---|
| 1 | Query Databricks Unity Catalog from AWS Lambda with DuckDB | _coming soon_ |
| 2 | Performance tuning: AWS Lambda Power Tuning + API Gateway cache | _coming soon_ |
| 3 | DuckDB meets Iceberg REST Catalog: what works, what doesn't (yet) | _coming soon_ |

---

## License

MIT
