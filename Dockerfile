# syntax=docker/dockerfile:1

ARG PYTHON_VERSION=3.12

# ---------- base ----------
FROM python:${PYTHON_VERSION}-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

EXPOSE 8080

# ---------- dev ----------
FROM base AS dev

COPY requirements-dev.txt .
RUN pip install -r requirements-dev.txt

COPY . .

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8080", "--reload"]

# ---------- prod ----------
FROM base AS prod

ARG SOURCE_REPO=""
LABEL org.opencontainers.image.source="${SOURCE_REPO}"

RUN groupadd --system app && useradd --system --gid app --no-create-home app

COPY --chown=app:app . .

USER app

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8080"]
