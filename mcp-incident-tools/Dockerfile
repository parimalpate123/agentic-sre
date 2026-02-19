FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY src/ /app/src/
COPY pyproject.toml /app/

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
    fastapi>=0.109.0 \
    uvicorn>=0.27.0 \
    pydantic>=2.0.0

ENV PYTHONPATH=/app/src

EXPOSE 8010

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8010/health || exit 1

CMD ["uvicorn", "incident_mcp_server.server:http_app", "--host", "0.0.0.0", "--port", "8010"]
