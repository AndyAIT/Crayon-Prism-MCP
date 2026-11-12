FROM python:3.12-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# Copy dependency definitions
COPY pyproject.toml uv.lock ./

# Install dependencies into the project environment
RUN uv sync --frozen --no-dev --no-install-project

# Copy application source
COPY server.py prism_client.py ./

# Configure Python environment
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV MCP_TRANSPORT=streamable-http

EXPOSE 8785

CMD ["python", "server.py"]
