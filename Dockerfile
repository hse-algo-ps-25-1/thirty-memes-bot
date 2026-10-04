FROM python:3.14-slim

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0 \
    PYTHONUNBUFFERED=1

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock .python-version README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev

COPY algorithms ./algorithms

CMD ["uv", "run", "--frozen", "--no-dev", "thirty-memes-bot"]
