FROM python:3.12-slim

RUN pip install --no-cache-dir "mlflow>=2.17" "psycopg2-binary>=2.9"

COPY docker/mlflow/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 5000
ENTRYPOINT ["/entrypoint.sh"]
