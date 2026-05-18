#!/bin/sh
set -e
exec mlflow server \
    --host 0.0.0.0 \
    --port 5000 \
    --backend-store-uri "${MLFLOW_BACKEND_STORE_URI}" \
    --artifacts-destination "${MLFLOW_DEFAULT_ARTIFACT_ROOT:-/mlflow/artifacts}" \
    --default-artifact-root "mlflow-artifacts:/" \
    --serve-artifacts \
    --allowed-hosts "${MLFLOW_ALLOWED_HOSTS:-localhost}"
