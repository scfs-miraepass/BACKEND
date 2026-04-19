FROM python:3.14-slim@sha256:557811b1000883f3c2bed1ad0e7b6c7a2fe8b4c4966c6ad26107e0ea4e62070f

# UV Install
COPY --from=ghcr.io/astral-sh/uv@sha256:733b4042187702f832f7fdecb3aff14a61b288c4ca37af188bb5715c1caebaf8 /uv /uvx /bin/

WORKDIR /app

# Copy the project into the image
COPY . .

# Disable development dependencies
ENV UV_NO_DEV=1

# System update and Sync the projec tinto a new environment
RUN apt-get update \
    && uv sync --locked

EXPOSE 8000

# DB 생성 및 실행
CMD ["sh", "-c", "uv run alembic upgrade head && uv run fastapi run"]