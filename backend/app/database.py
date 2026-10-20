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


def _add_missing_columns(conn, table: str, columns: dict[str, str]) -> None:
    present = {c["name"] for c in inspect(conn).get_columns(table)}
    for name, ddl in columns.items():
        if name not in present:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))


def _make_debtor_nullable_sqlite(conn) -> None:
    """SQLite не умеет снимать NOT NULL с колонки, поэтому пересоздаём таблицу и переносим данные."""
    info = conn.execute(text("PRAGMA table_info(expense_shares)")).fetchall()
    debtor = next((row for row in info if row[1] == "debtor_id"), None)
    if debtor is None or not debtor[3]:  # row[3] = notnull
        return
    # Индексы старой таблицы нужно удалить, иначе их имена займут место у новой
    for _, index_name, *_ in conn.execute(text("PRAGMA index_list(expense_shares)")).fetchall():
        if index_name.startswith("ix_"):
            conn.execute(text(f'DROP INDEX IF EXISTS "{index_name}"'))
    old_columns = [row[1] for row in info]
    conn.execute(text("ALTER TABLE expense_shares RENAME TO expense_shares_old"))
    Base.metadata.tables["expense_shares"].create(conn)
    new_columns = set(Base.metadata.tables["expense_shares"].columns.keys())
    shared = ", ".join(c for c in old_columns if c in new_columns)
    conn.execute(text(f"INSERT INTO expense_shares ({shared}) SELECT {shared} FROM expense_shares_old"))
    conn.execute(text("DROP TABLE expense_shares_old"))


def ensure_schema(bind=None) -> None:
    """Добавляет новые колонки в уже существующие таблицы.

    create_all создаёт только отсутствующие таблицы и не меняет старые. Поэтому, если у вас
    уже есть база от прошлой версии, недостающие колонки добавляем здесь вручную.
    """
    bind = bind or engine
    with bind.begin() as conn:
        _add_missing_columns(conn, "expenses", {"paid_total": "NUMERIC(12, 2)"})
        _add_missing_columns(
            conn,
            "expense_shares",
            {"debtor_name": "VARCHAR(60)", "reminded_at": "DATETIME", "remind_count": "INTEGER NOT NULL DEFAULT 0"},
        )
        # Друг без аккаунта: debtor_id теперь может быть пустым
        if conn.dialect.name == "sqlite":
            _make_debtor_nullable_sqlite(conn)
        else:
            conn.execute(text("ALTER TABLE expense_shares ALTER COLUMN debtor_id DROP NOT NULL"))
