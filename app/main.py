"""Точка входа FastAPI."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .config import BASE_DIR
from .database import init_db
from .routers import admin, auth, jobs, pages, public
from .seed import seed


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    seed()
    yield


app = FastAPI(title="PhotoClean", docs_url="/api/docs", redoc_url=None, lifespan=lifespan)

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "app" / "static")), name="static")

app.include_router(pages.router)
app.include_router(auth.router)
app.include_router(public.router)
app.include_router(jobs.router)
app.include_router(admin.router)


@app.get("/health")
def health():
    return {"status": "ok"}
