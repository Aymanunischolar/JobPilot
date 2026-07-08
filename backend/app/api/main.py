import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.agents.manager import close_checkpoint_pool
from app.api.admin_routes import router as admin_router
from app.api.routes import router
from app.core import admin_store

logger = logging.getLogger("jobpilot")
logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    close_checkpoint_pool()
    admin_store.close_pool()


app = FastAPI(
    title="JobPilot",
    description=(
        "A supervised multi-agent system for job discovery, ATS scoring, "
        "and resume tailoring — with a human approval gate before any "
        "external action."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catches anything that slips past a route's own error handling.
    The client gets a generic message and a request_id to quote when
    reporting the issue; the real exception (with traceback) goes to the
    server log only — internal details (stack traces, file paths,
    connection strings in an error message) should never reach a client
    response."""
    request_id = uuid.uuid4().hex[:12]
    logger.exception("Unhandled exception [request_id=%s]", request_id)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "An unexpected error occurred. Please try again.",
            "request_id": request_id,
        },
    )


app.include_router(router, prefix="/api")
app.include_router(admin_router, prefix="/api/admin", tags=["admin"])


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
