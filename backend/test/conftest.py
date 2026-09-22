import pytest
from fastapi import BackgroundTasks
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base, get_db

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session():
    # Bind and create all tables in in-memory SQLite
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session, monkeypatch):
    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    # TestClient executes BackgroundTasks synchronously as part of the request,
    # unlike a real ASGI server where they run after the response is sent. Since
    # POST /work-items now auto-queues AI analysis, leaving this wired up would
    # let every item creation silently advance past RECEIVED before test code
    # gets to run its own assertions/transitions. No-op it here; tests that need
    # to exercise AI analysis call WorkItemService.process_ai_analysis directly.
    monkeypatch.setattr(BackgroundTasks, "add_task", lambda self, *args, **kwargs: None)

    app.dependency_overrides[get_db] = _override_get_db
    # raise_server_exceptions=True forces Pytest to print the real backend exception
    with TestClient(app, raise_server_exceptions=True) as test_client:
        yield test_client
    app.dependency_overrides.clear()