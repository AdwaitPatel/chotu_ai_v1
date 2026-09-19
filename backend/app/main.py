from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import voice
from app.api.routes.speech import router as speech_router
from app.api.routes.payments import router as payments_router
from app.api.routes.v1 import router as v1_router
from app.api.routes.dashboard import router as dashboard_router
from app.core.config import get_settings
from app.core.database import engine
from app.core.exceptions import DomainError, domain_error_handler, integrity_error_handler
from app.core.logging import RequestLogMiddleware, configure_logging
from sqlalchemy.exc import IntegrityError

settings = get_settings()
configure_logging()

@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    await engine.dispose()


app = FastAPI(title=settings.APP_NAME, debug=settings.DEBUG, lifespan=lifespan)
app.add_middleware(RequestLogMiddleware)
app.add_exception_handler(DomainError, domain_error_handler)
app.add_exception_handler(IntegrityError, integrity_error_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(v1_router)
app.include_router(voice.router)
app.include_router(speech_router)
app.include_router(payments_router)
app.include_router(dashboard_router)


@app.get("/health")
async def health():
    return {"status": "ok", "app": settings.APP_NAME}


# Keep this last: a root StaticFiles mount would otherwise shadow API routes.
app.mount("/", StaticFiles(directory="app/static", html=True), name="frontend")
