# Deploy Guide — UC Reader Lambda

Questa guida descrive come buildare il Lambda Layer e deployare lo stack CDK su AWS.

## Prerequisiti

| Tool | Versione minima | Note |
|------|----------------|-------|
| Python | 3.12 | Per CDK e Lambda runtime |
| Node.js | 20 / 22 / 24 | Richiesto da CDK CLI |
| AWS CDK CLI | 2.1105.0+ | `npm install -g aws-cdk@latest` |
| Docker / Podman | qualsiasi | Per buildare il layer |
| AWS CLI | 2.x | Configurato con profilo `mylabs` |

## Struttura del progetto

```
databricks-uc-duckdb-lambda/
├── uc_reader.py                     # Lambda handler
├── requirements.txt                 # Deps locali (test)
├── DEPLOY.md                        # Questa guida
└── infra/
    ├── app.py                       # Entry point CDK
    ├── cdk.json
    ├── requirements.txt             # aws-cdk-lib
    ├── .venv/                       # Virtualenv CDK (gitignored)
    ├── stacks/
    │   └── uc_reader_stack.py       # Stack CDK
    └── lambda_layer/
        ├── build_layer.sh           # Script di build
        ├── dist/layer.zip           # Output build (gitignored)
        └── docker/
            └── Dockerfile
```

## Step 1 — Parametri SSM (una tantum)

Crea i parametri su AWS Parameter Store prima del primo deploy.

```bash
# Workspace Databricks — String (non cifrato)
aws ssm put-parameter \
  --name "/uc-reader/databricks-workspace" \
  --value "https://<your-workspace>.cloud.databricks.com" \
  --type String \
  --profile mylabs --region eu-central-1

# Token Databricks — SecureString (cifrato con KMS)
aws ssm put-parameter \
  --name "/uc-reader/databricks-token" \
  --value "dapi..." \
  --type SecureString \
  --profile mylabs --region eu-central-1
```

Per aggiornare un parametro esistente aggiungi `--overwrite`.

## Step 2 — Build del Lambda Layer

Il layer contiene `duckdb`, `pyarrow` e `requests` compilati per `linux/amd64`.

```bash
cd infra/lambda_layer
./build_layer.sh
```

Output: `infra/lambda_layer/dist/layer.zip` (~62MB zippato).

> **Versioni usate:** `duckdb 1.4.4`, `pyarrow 20.0.0`, `requests 2.32.5`
>
> `duckdb >= 1.4.4` è necessario per supportare `V2Checkpoint` delle tabelle Delta create da Databricks.
>
> Per usare versioni diverse:
> ```bash
> DUCKDB_VERSION=1.4.4 PYARROW_VERSION=20.0.0 ./build_layer.sh
> ```

## Step 3 — Setup ambiente CDK

```bash
cd infra
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Step 4 — Bootstrap CDK (una tantum per account/region)

```bash
AWS_PROFILE=mylabs CDK_DEFAULT_REGION=eu-central-1 cdk bootstrap
```

## Step 5 — Deploy

```bash
AWS_PROFILE=mylabs CDK_DEFAULT_REGION=eu-central-1 \
  cdk deploy --app ".venv/bin/python app.py" --require-approval never
```

## Step 6 — Test invoke

```bash
aws lambda invoke \
  --function-name <FunctionName dall'output CDK> \
  --payload '{"table":"catalog.schema.table","filters":"age = 30","limit":5}' \
  --cli-binary-format raw-in-base64-out \
  --region eu-central-1 --profile mylabs \
  /tmp/response.json && cat /tmp/response.json
```

## Aggiornamento

Per aggiornare solo il codice Lambda (senza rebuildare il layer):

```bash
./deploy.sh --skip-layer
```

Per aggiornare anche il layer:

```bash
./deploy.sh
```

## Cleanup

```bash
AWS_PROFILE=mylabs CDK_DEFAULT_REGION=eu-central-1 \
  cdk destroy --app ".venv/bin/python app.py"
```

## Note

- Il token Databricks è cifrato su SSM con KMS AWS managed (gratuito)
- La Lambda legge SSM a runtime via boto3 — nessun segreto in chiaro nell'infra
- Il layer è buildato per `linux/amd64` — non usare ARM per questa Lambda
- `boto3` è pre-installato nel runtime Lambda, non serve nel layer
- Su Lambda non esiste una home directory: il codice imposta `HOME=/tmp` prima dell'import di duckdb
- La regione S3 per i dati UC è `eu-west-1` (separata dalla region della Lambda `eu-central-1`)
