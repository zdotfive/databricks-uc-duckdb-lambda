#!/usr/bin/env bash
# Build del Lambda Layer con duckdb + pyarrow + requests
# Output: layer.zip pronto per il deploy CDK

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_DIR="${SCRIPT_DIR}/dist"

DUCKDB_VERSION="${DUCKDB_VERSION:-1.4.4}"
PYARROW_VERSION="${PYARROW_VERSION:-20.0.0}"
REQUESTS_VERSION="${REQUESTS_VERSION:-2.32.5}"
PYTHON_VERSION="${PYTHON_VERSION:-3.12}"

echo "Building Lambda Layer..."
echo "  duckdb    : ${DUCKDB_VERSION}"
echo "  pyarrow   : ${PYARROW_VERSION}"
echo "  requests  : ${REQUESTS_VERSION}"
echo "  python    : ${PYTHON_VERSION}"

mkdir -p "${OUTPUT_DIR}"

docker build \
    --platform linux/amd64 \
    --build-arg PYTHON_VERSION="${PYTHON_VERSION}" \
    --build-arg DUCKDB_VERSION="${DUCKDB_VERSION}" \
    --build-arg PYARROW_VERSION="${PYARROW_VERSION}" \
    --build-arg REQUESTS_VERSION="${REQUESTS_VERSION}" \
    -t duckdb-layer-builder \
    "${SCRIPT_DIR}/docker"

# Estrae il layer.zip dal container
CONTAINER_ID=$(docker create duckdb-layer-builder)
docker cp "${CONTAINER_ID}:/tmp/layer.zip" "${OUTPUT_DIR}/layer.zip"
docker rm "${CONTAINER_ID}"

echo ""
echo "Layer built: ${OUTPUT_DIR}/layer.zip"
echo "Size: $(du -sh "${OUTPUT_DIR}/layer.zip" | cut -f1)"
