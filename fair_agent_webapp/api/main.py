import os
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Add the parent directory (fair_agent_webapp/) to sys.path so
# fair_agent_core.py is importable from both the main process and
# background worker threads.
_HERE = os.path.dirname(os.path.abspath(__file__))
_CORE_DIR = os.path.dirname(_HERE)   # fair_agent_webapp/
if _CORE_DIR not in sys.path:
    sys.path.insert(0, _CORE_DIR)

from database import engine  # noqa: E402
import models                # noqa: E402
from routers import assessments  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs("data", exist_ok=True)
    models.Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="FAIR Studio API",
    version="1.0.0",
    description="Backend API for the FAIR Agent Assessment Studio",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(assessments.router, prefix="/api/assessments", tags=["Assessments"])


@app.get("/api/health", tags=["Health"])
def health():
    return {"status": "ok", "version": "1.0.0"}
