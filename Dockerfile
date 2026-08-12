# syntax=docker/dockerfile:1

FROM ghcr.io/sparfenyuk/mcp-proxy:v0.12.0

LABEL org.opencontainers.image.title="Folklore Variant Evidence MCP bridge"
LABEL org.opencontainers.image.description="Read-only stdio bridge to the public Folklore Streamable HTTP MCP endpoint"
LABEL org.opencontainers.image.source="https://github.com/helena-bioinformatics/folklore-mcp"
LABEL org.opencontainers.image.vendor="Helena Bioinformatics"

RUN addgroup -S folklore && adduser -S -G folklore folklore

USER folklore

CMD ["--transport", "streamablehttp", "--log-level", "WARNING", "https://api.helena.bio/folklore/v1/mcp"]
