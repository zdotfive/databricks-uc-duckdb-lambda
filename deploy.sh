#!/usr/bin/env bash
# Deploy completo: build layer + CDK deploy
# Usage:
#   ./deploy.sh              # build layer + deploy
#   ./deploy.sh --skip-layer # solo CDK deploy (layer già buildato)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AWS_PROFILE="${AWS_PROFILE:-mylabs}"
AWS_REGION="${AWS_REGION:-eu-central-1}"
SKIP_LAYER=false

for arg in "$@"; do
  [[ "$arg" == "--skip-layer" ]] && SKIP_LAYER=true
done

echo "========================================"
echo "  UC Reader Lambda — Deploy"
echo "  Profile : ${AWS_PROFILE}"
echo "  Region  : ${AWS_REGION}"
echo "  Layer   : $([ "$SKIP_LAYER" = true ] && echo 'SKIP' || echo 'BUILD')"
echo "========================================"

# ---------------------------------------------------------------------------
# Step 1 — Build layer
# ---------------------------------------------------------------------------
if [ "$SKIP_LAYER" = false ]; then
  echo ""
  echo "[1/3] Building Lambda Layer..."
  bash "${SCRIPT_DIR}/infra/lambda_layer/build_layer.sh"
else
  echo ""
  echo "[1/3] Skipping layer build."
  if [ ! -f "${SCRIPT_DIR}/infra/lambda_layer/dist/layer.zip" ]; then
    echo "ERROR: layer.zip non trovato. Esegui senza --skip-layer."
    exit 1
  fi
fi

# ---------------------------------------------------------------------------
# Step 2 — Setup venv CDK
# ---------------------------------------------------------------------------
echo ""
echo "[2/3] Setup ambiente CDK..."
VENV="${SCRIPT_DIR}/infra/.venv"
if [ ! -d "$VENV" ]; then
  python3 -m venv "$VENV"
fi
"${VENV}/bin/pip" install -r "${SCRIPT_DIR}/infra/requirements.txt" -q

# ---------------------------------------------------------------------------
# Step 3 — CDK deploy
# ---------------------------------------------------------------------------
echo ""
echo "[3/3] CDK deploy..."
cd "${SCRIPT_DIR}/infra"
AWS_PROFILE="${AWS_PROFILE}" CDK_DEFAULT_REGION="${AWS_REGION}" \
  cdk deploy --app "${VENV}/bin/python app.py" --require-approval never

echo ""
echo "========================================"
echo "  Deploy completato!"
echo "========================================"
