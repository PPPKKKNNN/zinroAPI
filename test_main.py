import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

from main import app, get_session
from models import User
from uuid import uuid4


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(session: Session):
    def get_session_override():
        return session

    app.dependency_overrides[get_session] = get_session_override
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


def test_create_user(client: TestClient):
    response = client.post("/users/", json={"name": "Tommy", "alias": "Friday"})
    data = response.json()

    assert response.status_code == 200
    assert data["name"] == "Tommy"
    assert data["alias"] == "Friday"
    assert data["id"] is not None


def test_create_user_incomplete(client: TestClient):
    # No name
    response = client.post("/users/", json={"alias": "Friday"})
    assert response.status_code == 422


def test_create_user_invalid(client: TestClient):
    # alias has an invalid type
    response = client.post(
        "/users/",
        json={
            "name": "Friday",
            "alias": {"message": "Do you wanna know my secret identity?"},
        },
    )
    assert response.status_code == 422


def test_read_users(session: Session, client: TestClient):
    user_1 = User(name="Deadpond", alias="Dive Wilson", session_token=str(uuid4()))
    print(user_1)
    user_2 = User(name="Rusty-Man", session_token=str(uuid4()))
    session.add(user_1)
    session.add(user_2)
    session.commit()

    client.cookies.set("session_token", user_1.session_token)
    response = client.get("/users/")
    data = response.json()

    assert response.status_code == 200
    assert len(data) == 2
    assert data[0]["alias"] == user_1.alias
    assert data[0]["id"] == user_1.id
    assert data[1]["alias"] == user_2.alias
    assert data[1]["id"] == user_2.id


def test_read_me(session: Session, client: TestClient):
    user_1 = User(name="Deadpond", alias="Dive Wilson", session_token=str(uuid4()))
    session.add(user_1)
    session.commit()

    client.cookies.set("session_token", user_1.session_token)
    response = client.get(f"/me/")
    data = response.json()

    assert response.status_code == 200
    assert data["name"] == user_1.name
    assert data["alias"] == user_1.alias
    assert data["id"] == user_1.id
