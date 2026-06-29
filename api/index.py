from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import os

from api.database import engine, Base
from api.models import Category, Transaction  # noqa: F401 — registers models with Base
from api.routers import categories, transactions, summary, import_route

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Expense Tracker", version="1.0.0")

# On Vercel, ALLOWED_ORIGIN should be set to your production domain.
# For local dev (no env var set), wildcard is used.
_allowed_origins_env = os.environ.get("ALLOWED_ORIGIN", "*")
_allowed_origins = (
    ["*"] if _allowed_origins_env == "*"
    else [o.strip() for o in _allowed_origins_env.split(",") if o.strip()]
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Accept"],
)

app.include_router(categories.router)
app.include_router(transactions.router)
app.include_router(summary.router)
app.include_router(import_route.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}


# Serve frontend static files in local dev only (Vercel serves them via CDN).
if not os.environ.get("VERCEL"):
    frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
    if os.path.exists(frontend_path):
        app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
