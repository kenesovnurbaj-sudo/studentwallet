import os

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# По умолчанию SQLite-файл. Для PostgreSQL задайте переменную окружения, например:
# DATABASE_URL=postgresql+psycopg2://user:password@localhost:5432/studentwallet
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./studentwallet.db")

# Хостинги отдают адрес как postgres:// или postgresql://, а SQLAlchemy нужен явный драйвер.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = "postgresql+psycopg2://" + DATABASE_URL[len("postgres://"):]
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = "postgresql+psycopg2://" + DATABASE_URL[len("postgresql://"):]

IS_SQLITE = DATABASE_URL.startswith("sqlite")
connect_args = {"check_same_thread": False} if IS_SQLITE else {}
# pool_pre_ping: облачная база засыпает, и соединение перед использованием проверяется
engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_schema(bind=None) -> None:
    """Добавляет новые колонки в уже существующие таблицы.

    create_all создаёт только отсутствующие таблицы и не меняет старые. Поэтому, если у вас
    уже есть база от прошлой версии, колонку paid_total добавляем здесь вручную.
    """
    bind = bind or engine
    columns = {c["name"] for c in inspect(bind).get_columns("expenses")}
    if "paid_total" not in columns:
        with bind.begin() as conn:
            conn.execute(text("ALTER TABLE expenses ADD COLUMN paid_total NUMERIC(12, 2)"))
