#!/usr/bin/env bash
# Invoca la Lambda UC Reader e mostra il risultato
# Usage:
#   ./invoke.sh
#   ./invoke.sh --table "catalog.schema.table" --filters "age > 25" --limit 10

set -euo pipefail

FUNCTION_NAME="UcReaderStack-UcReaderFunction56CA7D68-aqROHbFjfzj4"
AWS_PROFILE="${AWS_PROFILE:-mylabs}"
AWS_REGION="${AWS_REGION:-eu-central-1}"
TABLE="${TABLE:-labs.duckdb_uc_test.first_table_iceberg}"
FILTERS="${FILTERS:-}"
LIMIT="${LIMIT:-10}"
OUTPUT="/tmp/lambda_response.json"

# Parsing args opzionali
while [[ $# -gt 0 ]]; do
  case $1 in
    --table)   TABLE="$2";   shift 2 ;;
    --filters) FILTERS="$2"; shift 2 ;;
    --limit)   LIMIT="$2";   shift 2 ;;
    *) echo "Unknown arg: $1"; exit 1 ;;
  esac
done

# Costruisce il payload JSON
if [ -n "$FILTERS" ]; then
  PAYLOAD="{\"table\":\"${TABLE}\",\"filters\":\"${FILTERS}\",\"limit\":${LIMIT}}"
else
  PAYLOAD="{\"table\":\"${TABLE}\",\"limit\":${LIMIT}}"
fi

echo "========================================"
echo "  Invoking Lambda"
echo "  Table   : ${TABLE}"
echo "  Filters : ${FILTERS:-—}"
echo "  Limit   : ${LIMIT}"
echo "========================================"

aws lambda invoke \
  --function-name "${FUNCTION_NAME}" \
  --payload "${PAYLOAD}" \
  --cli-binary-format raw-in-base64-out \
  --region "${AWS_REGION}" \
  --profile "${AWS_PROFILE}" \
  "${OUTPUT}" > /dev/null

python3 -c "
import json, sys
with open('${OUTPUT}') as f:
    r = json.load(f)
print('statusCode:', r['statusCode'])
body = json.loads(r['body'])
if r['statusCode'] == 200:
    print('rows   :', body['rows'])
    print('columns:', body['columns'])
    print()
    print(json.dumps(body['data'], indent=2, default=str))
else:
    print('ERROR:', body.get('error'))
    sys.exit(1)
"
