import json
import os

# Su Lambda non c'è una home directory — impostare HOME=/tmp prima
# di importare duckdb evita l'errore "Can't find the home directory"
os.environ.setdefault("HOME", "/tmp")

import boto3
import duckdb
import pyarrow as pa
import requests

# ---------------------------------------------------------------------------
# Config — letta da SSM Parameter Store a runtime (SecureString supportato)
# ---------------------------------------------------------------------------
AWS_REGION = "eu-west-1"   # region dove risiedono i dati S3 di Unity Catalog


def _load_config() -> tuple[str, str]:
    """Legge workspace e token da SSM Parameter Store."""
    ssm = boto3.client("ssm", region_name="eu-central-1")
    workspace = ssm.get_parameter(
        Name=os.environ["SSM_WORKSPACE"]
    )["Parameter"]["Value"]
    token = ssm.get_parameter(
        Name=os.environ["SSM_TOKEN"], WithDecryption=True
    )["Parameter"]["Value"]
    return workspace, token


WORKSPACE, TOKEN = _load_config()


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------

def _get_temp_credentials(table: str) -> tuple[str, dict]:
    """
    Chiama Unity Catalog e restituisce (s3_url, aws_temp_credentials).

    Parameters
    ----------
    table : str
        Full UC table name  ``catalog.schema.table``.

    Returns
    -------
    s3_url : str
        Percorso S3 della tabella.
    aws_creds : dict
        Credenziali temporanee AWS (access_key_id, secret_access_key, session_token).
    """
    headers = {"Authorization": f"Bearer {TOKEN}"}

    info = requests.get(
        f"{WORKSPACE}/api/2.1/unity-catalog/tables/{table}",
        headers=headers,
        timeout=10,
    ).json()

    creds = requests.post(
        f"{WORKSPACE}/api/2.1/unity-catalog/temporary-table-credentials",
        headers=headers,
        json={"table_id": info["table_id"], "operation": "READ"},
        timeout=10,
    ).json()

    return creds["url"], creds["aws_temp_credentials"]


def _make_duckdb_con(aws_creds: dict) -> duckdb.DuckDBPyConnection:
    """Crea una connessione DuckDB con credenziali S3 temporanee."""
    con = duckdb.connect(database=":memory:")
    con.execute("SET home_directory='/tmp';")
    con.execute("INSTALL delta; LOAD delta;")
    con.execute(f"""
        CREATE SECRET aws_temp (
            TYPE S3,
            KEY_ID        '{aws_creds["access_key_id"]}',
            SECRET        '{aws_creds["secret_access_key"]}',
            SESSION_TOKEN '{aws_creds["session_token"]}',
            REGION        '{AWS_REGION}'
        );
    """)
    return con


def read_uc_table(
    table: str,
    filters: str | None = None,
    limit: int | None = None,
) -> pa.Table:
    """
    Legge una tabella Unity Catalog (Delta) via DuckDB e restituisce PyArrow.

    Parameters
    ----------
    table : str
        Full UC table name  ``catalog.schema.table``.
    filters : str | None
        Condizione SQL opzionale, es. ``"age = 30"`` o ``"age > 25 AND name = 'Alice'"``.
    limit : int | None
        Righe massime (None = tutte).

    Returns
    -------
    pyarrow.Table
    """
    s3_url, aws_creds = _get_temp_credentials(table)
    con = _make_duckdb_con(aws_creds)

    query = f"SELECT * FROM delta_scan('{s3_url}')"
    if filters:
        query += f" WHERE {filters}"
    if limit is not None:
        query += f" LIMIT {limit}"

    return con.execute(query).arrow().read_all()


# ---------------------------------------------------------------------------
# AWS Lambda handler
# ---------------------------------------------------------------------------

def handler(event: dict, context) -> dict:
    """
    Lambda handler.

    Event payload
    -------------
    {
        "table":   "catalog.schema.table",  # obbligatorio (o env DEFAULT_TABLE)
        "filters": "age = 30",              # opzionale
        "limit":   100                      # opzionale
    }
    """
    table = event.get("table") or os.environ.get("DEFAULT_TABLE")
    if not table:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Missing 'table' in event or DEFAULT_TABLE env var"}),
        }

    filters = event.get("filters")
    limit   = int(event.get("limit", 100))

    try:
        arrow_table = read_uc_table(table, filters=filters, limit=limit)
        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "table":   table,
                    "rows":    arrow_table.num_rows,
                    "columns": arrow_table.schema.names,
                    "data":    arrow_table.to_pydict(),
                },
                default=str,
            ),
        }
    except Exception as exc:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(exc)}),
        }
