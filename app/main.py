from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.cards import router as cards_router
from app.api.routes.collections import router as collections_router
from app.api.routes.health import router as health_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.middleware.request_logging import RequestLoggingMiddleware

configure_logging(settings.log_level)

app = FastAPI(title=settings.app_name)

app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(cards_router)
app.include_router(collections_router)
