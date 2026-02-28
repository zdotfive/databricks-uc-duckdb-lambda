ARG PYTHON_VERSION=3.12
FROM --platform=linux/amd64 python:${PYTHON_VERSION}-slim

ARG DUCKDB_VERSION=1.4.4
ARG PYARROW_VERSION=20.0.0
ARG REQUESTS_VERSION=2.32.5

WORKDIR /tmp

RUN apt-get update && apt-get install -y zip && rm -rf /var/lib/apt/lists/*

RUN pip install \
    duckdb==${DUCKDB_VERSION} \
    pyarrow==${PYARROW_VERSION} \
    requests==${REQUESTS_VERSION} \
    --no-cache-dir -t /tmp/python

RUN zip -r /tmp/layer.zip python
