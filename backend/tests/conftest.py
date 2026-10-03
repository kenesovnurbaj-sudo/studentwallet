import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import Role, User
from app.security import hash_password
from app.seed import seed


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with TestingSession() as db:
        seed(db)
        yield db


@pytest.fixture()
def client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def register_and_login(client: TestClient, email: str = "student@example.com") -> dict:
    client.post("/api/auth/register", json={"email": email, "password": "password123", "full_name": "Test"})
    token = client.post("/api/auth/login", json={"email": email, "password": "password123"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def auth_headers(client):
    return register_and_login(client)


@pytest.fixture()
def admin_headers(client, db_session):
    admin_role = db_session.query(Role).filter_by(name="admin").one()
    db_session.add(User(email="admin@example.com", password_hash=hash_password("password123"), role_id=admin_role.id))
    db_session.commit()
    token = client.post("/api/auth/login", json={"email": "admin@example.com", "password": "password123"}).json()[
        "access_token"
    ]
    return {"Authorization": f"Bearer {token}"}
