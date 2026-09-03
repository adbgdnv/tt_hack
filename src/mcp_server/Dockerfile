# Собирается из корня репозитория: docker build -f src/mcp_server/Dockerfile .
FROM python:3.12-slim AS builder

WORKDIR /build
COPY pyproject.toml ./
COPY src/ ./src/
RUN pip install --no-cache-dir --prefix=/install .

FROM python:3.12-slim

WORKDIR /app
COPY --from=builder /install /usr/local
COPY src/ ./src/

ENV PYTHONPATH=/app/src
EXPOSE 8001

CMD ["python", "src/mcp_server/server.py"]
