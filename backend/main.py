"""
OpenClaw-Py — composition root.

Run: uvicorn main:app --reload --port 8000

main.py knows nothing about any specific module. It mounts the auth router,
the providers router, every module router in the registry, and a small meta
endpoint so the frontend can discover modules.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import APP_NAME, APP_VERSION, CORS_ORIGINS
from core.setup_routes import router as setup_router
from auth.routes import router as auth_router
from providers.routes import router as providers_router
from modules import mount_all, meta_router

app = FastAPI(title=f"{APP_NAME} API", version=APP_VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global routers
app.include_router(setup_router)
app.include_router(auth_router)
app.include_router(providers_router)
app.include_router(meta_router)

# All registered modules
mount_all(app)


@app.get("/")
def root():
    return {"app": APP_NAME, "version": APP_VERSION, "status": "running"}
