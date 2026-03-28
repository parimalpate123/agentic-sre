FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir elasticsearch-mcp-server

EXPOSE 8020

HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=3 \
    CMD curl -sf http://localhost:8020/mcp || exit 1

CMD ["elasticsearch-mcp-server", "--transport", "streamable-http", "--host", "0.0.0.0", "--port", "8020", "--path", "/mcp"]
