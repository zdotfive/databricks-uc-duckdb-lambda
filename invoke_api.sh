#!/usr/bin/env bash
# Invoca l'API Gateway UC Reader e mostra il risultato
# Usage:
#   ./invoke_api.sh
#   ./invoke_api.sh --table "catalog.schema.table" --filters "customerID = 2033056" --limit 10

set -euo pipefail

API_URL="${API_URL:-https://<api-id>.execute-api.<region>.amazonaws.com/prod/query}"
TABLE="${TABLE:-catalog.schema.table}"
FILTERS="${FILTERS:-}"
LIMIT="${LIMIT:-10}"

# Parsing args opzionali
while [[ $# -gt 0 ]]; do
  case $1 in
    --table)   TABLE="$2";   shift 2 ;;
    --filters) FILTERS="$2"; shift 2 ;;
    --limit)   LIMIT="$2";   shift 2 ;;
    *) echo "Unknown arg: $1"; exit 1 ;;
  esac
done

# URL-encode parametri
TABLE_ENC=$(python3 -c "import urllib.parse; print(urllib.parse.quote('${TABLE}'))")
LIMIT_ENC="${LIMIT}"

URL="${API_URL}?table=${TABLE_ENC}&limit=${LIMIT_ENC}"
if [ -n "$FILTERS" ]; then
  FILTERS_ENC=$(python3 -c "import urllib.parse; print(urllib.parse.quote('${FILTERS}'))")
  URL="${URL}&filters=${FILTERS_ENC}"
fi

echo "========================================"
echo "  Invoking API Gateway"
echo "  URL     : ${URL}"
echo "  Table   : ${TABLE}"
echo "  Filters : ${FILTERS:-—}"
echo "  Limit   : ${LIMIT}"
echo "========================================"

HTTP_CODE=$(curl -s -o /tmp/api_response.json -w "%{http_code}" \
  -H "Accept: application/json" \
  "${URL}")

python3 -c "
import json, sys
with open('/tmp/api_response.json') as f:
    r = json.load(f)
print('statusCode:', ${HTTP_CODE})
if ${HTTP_CODE} == 200:
    print('rows   :', r['rows'])
    print('columns:', r['columns'])
    print()
    print(json.dumps(r['data'], indent=2, default=str))
else:
    print('ERROR:', r.get('error', r))
    sys.exit(1)
"
