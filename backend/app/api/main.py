from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.agents.manager import close_checkpoint_pool
from app.api.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    close_checkpoint_pool()


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

app.include_router(router, prefix="/api")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
