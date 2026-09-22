FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml .
COPY app ./app
COPY alembic.ini .
COPY migrations ./migrations
RUN pip install --no-cache-dir .

RUN mkdir -p /app/data
EXPOSE 8000
