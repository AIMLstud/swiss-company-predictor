FROM apache/airflow:2.10.4-python3.12

# Install project extras into the airflow user's Python environment.
# PythonVirtualenvOperator tasks use system_site_packages=True and therefore
# inherit these packages without re-installing on every task run.
WORKDIR /opt/airflow
COPY --chown=airflow:root pyproject.toml ./
COPY --chown=airflow:root src/ ./src/

RUN pip install --no-cache-dir ".[scraper,features,training]"
