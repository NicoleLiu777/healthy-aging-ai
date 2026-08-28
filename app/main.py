from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.ask import router as ask_router
from app.api.routes.evidence import router as evidence_router
from app.api.routes.health import router as health_router
from app.core.config import Settings, get_settings
from app.http_boundary import RequestBodyLimitMiddleware, SecurityHeadersMiddleware


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    docs_url = "/docs" if settings.api_docs_enabled else None
    openapi_url = "/openapi.json" if settings.api_docs_enabled else None

    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "Evidence-to-decision backend for health product and care teams. "
            "Not a consumer health chatbot."
        ),
        docs_url=docs_url,
        redoc_url=None,
        openapi_url=openapi_url,
    )

    application.add_middleware(
        RequestBodyLimitMiddleware,
        max_body_bytes=settings.max_request_body_bytes,
    )
    application.add_middleware(SecurityHeadersMiddleware)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type"],
    )

    application.include_router(health_router)
    application.include_router(evidence_router)
    application.include_router(ask_router)
    return application


app = create_app()
