# Build from repository root: docker build -f mcp_server/Dockerfile -t maliaras-parent-mcp:0.1.0 .
FROM ghcr.io/astral-sh/uv:0.10.4 AS uv
FROM python:3.12-slim
COPY --from=uv /uv /usr/local/bin/uv
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates tzdata \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --uid 10001 --create-home app
WORKDIR /app/mcp_server
COPY mcp_server/pyproject.toml mcp_server/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project && rm -rf /root/.cache
# report_md uses report_pdf's HTML-to-text helper; ReportLab is lazily imported
# only by the unused PDF writer, so no PDF runtime dependency is installed.
COPY client.py lessons.py report_md.py report_pdf.py report_format.py /app/
COPY mcp_server/service.py mcp_server/server.py mcp_server/instructions.md ./
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 FASTMCP_ENABLE_RICH_TRACEBACKS=false
USER 10001:10001
EXPOSE 8000
CMD ["/app/mcp_server/.venv/bin/python", "server.py"]
