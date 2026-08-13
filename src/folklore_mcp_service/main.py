"""FastAPI composition for the default-disabled Folklore MCP service."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

from folklore_mcp_service.application.gateway import VariantGateway
from folklore_mcp_service.application.literature_gateway import LiteratureGateway
from folklore_mcp_service.config.settings import Settings, get_settings
from folklore_mcp_service.presentation.mcp import (
    MCP_ADAPTER_VERSION,
    FolkloreMcpApplication,
    create_mcp_app,
)


def _configure_logging(settings: Settings) -> None:
    logging.basicConfig(level=settings.LOG_LEVEL, force=True)
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.add_log_level,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, settings.LOG_LEVEL)
        ),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def create_app(
    settings: Settings | None = None,
    *,
    gateway: VariantGateway | None = None,
    literature_gateway: LiteratureGateway | None = None,
    metrics_registry: CollectorRegistry | None = None,
) -> FastAPI:
    application_settings = settings or get_settings()
    _configure_logging(application_settings)
    logger = structlog.get_logger()
    variant_gateway = gateway or VariantGateway(application_settings)
    public_literature_gateway = literature_gateway or LiteratureGateway(
        application_settings
    )
    registry = metrics_registry or CollectorRegistry()
    requests = Counter(
        "folklore_mcp_tool_calls_total",
        "Folklore MCP tool calls by closed outcome.",
        ("outcome",),
        registry=registry,
    )
    duration = Histogram(
        "folklore_mcp_tool_duration_seconds",
        "Folklore MCP tool call duration by closed outcome.",
        ("outcome",),
        registry=registry,
    )
    enabled = Gauge(
        "folklore_mcp_capability_enabled",
        "Whether the Folklore MCP capability is configured as enabled.",
        registry=registry,
    )
    enabled.set(int(application_settings.FOLKLORE_MCP_ENABLED))

    def observe(outcome: str, elapsed: float) -> None:
        allowed = {
            "resolved",
            "ambiguous",
            "not_found",
            "invalid_request",
            "unsupported",
            "resolution_unavailable",
            "upstream_timeout",
            "upstream_unavailable",
            "invalid_upstream_response",
            "internal_failure",
        }
        safe_outcome = outcome if outcome in allowed else "internal_failure"
        requests.labels(outcome=safe_outcome).inc()
        duration.labels(outcome=safe_outcome).observe(elapsed)

    mcp_application: FolkloreMcpApplication | None = None
    if application_settings.FOLKLORE_MCP_ENABLED:
        mcp_application = create_mcp_app(
            gateway=variant_gateway,
            literature_gateway=public_literature_gateway,
            settings=application_settings,
            observe=observe,
        )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        fields = {
            "service": application_settings.SERVICE_NAME,
            "environment": application_settings.ENVIRONMENT.value,
        }
        logger.info("service_starting", **fields)
        try:
            if mcp_application is None:
                yield
            else:
                async with mcp_application.lifespan():
                    yield
        finally:
            await variant_gateway.close()
            await public_literature_gateway.close()
            logger.info("service_stopped", **fields)

    app = FastAPI(
        title="Folklore Clinical Variant Interpretation MCP Service",
        version=MCP_ADAPTER_VERSION,
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.metrics_registry = registry
    app.state.variant_gateway = variant_gateway
    app.state.literature_gateway = public_literature_gateway

    if mcp_application is not None:
        app.mount("/folklore/v1/mcp", mcp_application, name="folklore-mcp")

    @app.get("/folklore/v1/health")
    async def health() -> dict[str, str]:
        return {"status": "healthy", "service": application_settings.SERVICE_NAME}

    @app.get("/folklore/v1/ready")
    async def ready(response: Response) -> dict[str, object]:
        upstream_ready = await variant_gateway.ready()
        literature_ready = (
            await public_literature_gateway.ready()
            if application_settings.FOLKLORE_LITERATURE_ENABLED
            else None
        )
        is_ready = bool(
            application_settings.FOLKLORE_MCP_ENABLED
            and upstream_ready
            and (literature_ready is not False)
        )
        if not is_ready:
            response.status_code = 503
        return {
            "status": "ready" if is_ready else "not_ready",
            "service": application_settings.SERVICE_NAME,
            "dependencies": {
                "public_variant_search": upstream_ready,
                "public_variant_literature": literature_ready,
            },
        }

    @app.get("/metrics", include_in_schema=False)
    async def metrics() -> Response:
        return Response(
            content=generate_latest(registry),
            media_type=CONTENT_TYPE_LATEST,
        )

    return app


app = create_app()


def main() -> None:
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "folklore_mcp_service.main:app",
        host=settings.HOST,
        port=settings.PORT,
        log_level=settings.LOG_LEVEL.lower(),
        access_log=False,
    )


if __name__ == "__main__":
    main()
