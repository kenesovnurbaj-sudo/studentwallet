import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import Base, SessionLocal, engine
from .routers import admin, assistant, auth, budgets, categories, expenses, imports
from .migrations import move_people_to_transfers
from .seed import seed


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
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
app.include_router(budgets.router)
app.include_router(admin.router)
app.include_router(assistant.router)
app.include_router(imports.router)


@app.get("/api/health", tags=["system"])
def health():
    return {"status": "ok"}
