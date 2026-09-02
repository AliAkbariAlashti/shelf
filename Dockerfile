FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY shelf ./shelf

RUN pip install --no-cache-dir .

ENV SHELF_DB_PATH=/data/shelf.db
VOLUME ["/data"]

EXPOSE 8000

CMD ["shelf", "serve", "--host", "0.0.0.0", "--port", "8000"]
