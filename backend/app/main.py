from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import Base, SessionLocal, engine
from .routers import admin, auth, budgets, categories, expenses
from .seed import seed


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed(db)
    yield


app = FastAPI(title="StudentWallet API", version="0.1.0", lifespan=lifespan)

# Для разработки разрешаем запросы с frontend (Vite по умолчанию на порту 5173).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(categories.router)
app.include_router(expenses.router)
app.include_router(budgets.router)
app.include_router(admin.router)


@app.get("/api/health", tags=["system"])
def health():
    return {"status": "ok"}
