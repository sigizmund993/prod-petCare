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

# ---------- dev ----------
FROM base AS dev

COPY requirements-dev.txt .
RUN pip install -r requirements-dev.txt

# Локально код перекрывается volume'ом из docker-compose.dev.yml
COPY . .

# watchfiles перезапускает приложение при изменении .py файлов
CMD ["watchfiles", "--filter", "python", "python main.py", "/app"]

# ---------- prod ----------
FROM base AS prod

ARG SOURCE_REPO=""
LABEL org.opencontainers.image.source="${SOURCE_REPO}"

RUN groupadd --system app && useradd --system --gid app --no-create-home app

COPY --chown=app:app . .

USER app

CMD ["python", "main.py"]
