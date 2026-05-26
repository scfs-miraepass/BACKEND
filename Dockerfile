FROM python:3.14-slim

# UV Install
COPY --from=ghcr.io/astral-sh/uv /uv /uvx /bin/

WORKDIR /app

# Copy the project into the image
COPY . .

# Disable development dependencies
ENV UV_NO_DEV=1

# System update and Sync the projec tinto a new environment
RUN apt-get update \
    && uv sync --locked

EXPOSE 8000

# DB 마이그레이션 및 실행
CMD ['sh', '-c', 'uv run alembic upgrade head && uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips="*"']