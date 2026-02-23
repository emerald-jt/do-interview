import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import asyncio
from main import app
from db import Base
from models import ShortURL

# Create an in-memory SQLite async engine
SQLALCHEMY_TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"
engine_test = create_async_engine(
    SQLALCHEMY_TEST_DATABASE_URL, connect_args={"check_same_thread": False}, poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(engine_test, expire_on_commit=False, class_=AsyncSession)

async def override_get_db():
    async with TestingSessionLocal() as session:
        yield session

@pytest.fixture(scope="session", autouse=True)
def setup_database():
    # Create tables in the in-memory DB before any tests run
    async def create_tables():
        async with engine_test.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    asyncio.get_event_loop().run_until_complete(create_tables())
    yield


from main import get_db
app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

def test_shorten_and_redirect():
    # Test shortening a URL
    response = client.post("/shorten", json={"url": "https://example.com"})
    assert response.status_code == 200
    data = response.json()
    assert "code" in data
    code = data["code"]
    assert data["url"].rstrip("/") == "https://example.com"

    # Test redirect
    redirect_response = client.get(f"/{code}", follow_redirects=False)
    assert redirect_response.status_code == 307
    assert redirect_response.headers["location"].rstrip("/") == "https://example.com"

    # Test metadata
    meta_response = client.get(f"/meta/{code}")
    assert meta_response.status_code == 200
    meta = meta_response.json()
    assert meta["code"] == code
    assert meta["url"].rstrip("/") == "https://example.com"
    assert meta["hits"] == 1


def test_custom_alias():
    alias = "myalias123"
    response = client.post("/shorten", json={"url": "https://foo.com", "custom_alias": alias})
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == alias
    assert data["url"].rstrip("/") == "https://foo.com"

    # Duplicate alias should fail
    dup_response = client.post("/shorten", json={"url": "https://bar.com", "custom_alias": alias})
    assert dup_response.status_code == 409


def test_invalid_url():
    response = client.post("/shorten", json={"url": "not-a-url"})
    assert response.status_code == 422


def test_not_found():
    response = client.get("/meta/doesnotexist")
    assert response.status_code == 404
    response = client.get("/doesnotexist", follow_redirects=False)
    assert response.status_code == 404
