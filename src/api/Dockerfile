# Собирается из корня репозитория: docker build -f src/api/Dockerfile .
FROM python:3.12-slim AS builder

WORKDIR /build
COPY pyproject.toml ./
COPY src/ ./src/
RUN pip install --no-cache-dir --prefix=/install .

FROM python:3.12-slim

WORKDIR /app
COPY --from=builder /install /usr/local
COPY src/ ./src/

# data/ монтируется томом, а не копируется: выгрузка кейсодателя весит 4 МБ
# и в слои образа ей не место
ENV PYTHONPATH=/app/src
EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
