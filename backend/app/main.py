import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .database import Base, SessionLocal, engine, ensure_schema
from .migrations import move_people_to_transfers, rename_default_categories_to_english
from .routers import admin, ai, assistant, auth, budgets, categories, debts, expenses, imports
from .seed import seed


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    ensure_schema()
    with SessionLocal() as db:
        rename_default_categories_to_english(db)
        seed(db)
        move_people_to_transfers(db)
    yield


app = FastAPI(title="StudentWallet API", version="0.1.0", lifespan=lifespan)

# Для разработки разрешаем запросы с frontend (Vite по умолчанию на порту 5173).
# На сервере frontend и API на одном адресе (Nginx), CORS не нужен; при необходимости
# задайте CORS_ORIGINS через запятую.
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(categories.router)
app.include_router(expenses.router)
app.include_router(debts.router)
app.include_router(budgets.router)
app.include_router(admin.router)
app.include_router(assistant.router)
app.include_router(ai.router)
app.include_router(imports.router)


@app.get("/api/health", tags=["system"])
def health():
    return {"status": "ok"}


# На хостинге собранный сайт лежит в папке static (её кладёт Dockerfile).
# Локально её нет, и этот блок ничего не делает.
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

if STATIC_DIR.is_dir():
    if (STATIC_DIR / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_frontend(full_path: str):
        if full_path == "api" or full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found")
        candidate = (STATIC_DIR / full_path).resolve()
        if full_path and candidate.is_file() and STATIC_DIR.resolve() in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(STATIC_DIR / "index.html")
