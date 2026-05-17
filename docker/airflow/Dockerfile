FROM apache/airflow:2.10.4-python3.12

# Install third-party dependencies needed by DAG tasks.
# Our own source code is provided via PYTHONPATH=/opt/airflow/src (docker-compose.yml).
RUN pip install --no-cache-dir \
    "mlflow>=2.17" \
    "xgboost>=2.1" \
    "scikit-learn>=1.5" \
    "pandas>=2.2" \
    "psycopg[binary]>=3.2" \
    "pydantic-settings>=2.6" \
    "requests>=2.32" \
    "beautifulsoup4>=4.12"
