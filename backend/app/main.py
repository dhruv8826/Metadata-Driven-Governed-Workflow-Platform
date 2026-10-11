import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

from app.core.config import CORS_ORIGINS, MAX_PAYLOAD_BYTES, DB_PATH
from app.core.database import init_database
from app.scripts.seed_db import seed_database
from app.api import tenants, metadata, records, transitions, approvals, dashboards, audit

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure database is initialized and seeded on startup
    if not os.path.exists(DB_PATH):
        init_database(DB_PATH)
        seed_database(DB_PATH)
    yield

app = FastAPI(
    title="Metadata-Driven Governed Workflow Platform",
    description="Domain-agnostic, multi-tenant enterprise workflow and governance platform",
    version="1.0.0",
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Payload Size Guard Middleware (DDoS & Bloat Protection)
@app.middleware("http")
async def limit_payload_size(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > MAX_PAYLOAD_BYTES:
        return JSONResponse(
            status_code=413,
            content={"detail": "Payload too large. Maximum request size is 1MB."}
        )
    return await call_next(request)

# Include API Routers
app.include_router(tenants.router)
app.include_router(metadata.router)
app.include_router(records.router)
app.include_router(transitions.router)
app.include_router(approvals.router)
app.include_router(dashboards.router)
app.include_router(audit.router)

@app.get("/health")
def health_check():
    return {"status": "HEALTHY", "engine": "FastAPI + SQLite + Native JSON"}
