FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml ./
COPY src/ ./src/
COPY streamlit_app/ ./streamlit_app/

RUN pip install --no-cache-dir ".[streamlit-app]"

EXPOSE 8501

CMD ["streamlit", "run", "streamlit_app/app.py", \
     "--server.address=0.0.0.0", \
     "--server.port=8501", \
     "--server.headless=true"]
