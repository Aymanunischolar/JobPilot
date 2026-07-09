# Microsoft's official Playwright image ships Chromium + all matching OS
# deps pre-installed and version-pinned for this exact Playwright release —
# `playwright install --with-deps` on a generic python:slim image is
# fragile across Debian releases (font package names drift and break it).
FROM mcr.microsoft.com/playwright/python:v1.49.0-noble AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ backend/

WORKDIR /app/backend
ENV PYTHONPATH=/app/backend

EXPOSE 8000

CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
