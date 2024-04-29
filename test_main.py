import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

from main import app, get_session
from models import User, Room
from uuid import uuid4


# main.pyのテストは動的な要素が絡み、localhost以外のネットワークアクセスを制限する中程度のテスト範囲（GoogleのテストにおけるMiddleテスト）である。
# https://qiita.com/AHA_oretama/items/6239aac9eafd397ebf4e
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


def test_read_me_invalid(session: Session, client: TestClient):
    user_1 = User(name="Deadpond", alias="Dive Wilson", session_token=str(uuid4()))
    session.add(user_1)
    session.commit()

    response = client.get(f"/me/")
    data = response.json()

    assert response.status_code == 404


def test_create_room(client: TestClient):
    response = client.post(
        "/rooms/",
        json={"name": "room_1", "explanation": "This is explanationnof room_1."},
    )
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == "room_1"
    assert data["explanation"] == "This is explanationnof room_1."


def test_create_room_incomplete(client: TestClient):
    # No name
    response = client.post(
        "/rooms/", json={"explanation": "This is explanationnof room_1."}
    )
    assert response.status_code == 422


def test_create_room_invalid(client: TestClient):
    # alias has an invalid type
    response = client.post(
        "/rooms/",
        json={
            "name": "room_1",
            "explanation": {"message": "Do you wanna know my secret identity?"},
        },
    )
    assert response.status_code == 422


def test_read_rooms(session: Session, client: TestClient):
    room_1 = Room(name="room_1")
    room_2 = Room(name="room_2")
    room_3 = Room(name="room_3", explanation="room3 explanation")
    room_4 = Room(name="room_4")
    room_5 = Room(name="room_5")

    session.add(room_1)
    session.add(room_2)
    session.add(room_3)
    session.add(room_4)
    session.add(room_5)
    session.commit()

    params = {"offset": 1, "limit": 3}
    response = client.get("/rooms/", params=params)
    data = response.json()

    assert response.status_code == 200
    assert len(data) == 3
    assert data[0]["id"] == room_2.id
    assert data[0]["name"] == room_2.name
    assert data[0]["explanation"] == room_2.explanation
    assert data[0]["state"] == room_2.state
    assert data[0]["detail_of_role"] == room_2.detail_of_role
    assert data[0]["created_at"] == room_2.created_at.strftime("%Y-%m-%dT%H:%M:%S.%f")
    assert data[0]["updated_at"] == room_2.updated_at.strftime("%Y-%m-%dT%H:%M:%S.%f")
    assert data[0]["users"] == room_2.users

    # 説明文がある場合のテスト
    assert data[1]["explanation"] == room_3.explanation


# TODO update_room()のテスト
def test_update_room(session: Session, client: TestClient):
    room_1 = Room(name="room_1")
    session.add(room_1)
    session.commit()
    user_1 = User(
        name="Tommy", session_token=str(uuid4()), room_id=room_1.id, alias="Rustyman"
    )
    session.add(user_1)
    session.commit()

    json = {
        "name": "Hazbin Hotel",
        "explanation": "The best hotel in Hell",
        "detail_of_role": "devils",
    }
    client.cookies.set("session_token", user_1.session_token)
    response = client.patch(
        f"/rooms/",
        json=json,
    )
    data = response.json()

    assert response.status_code == 200
    assert data["name"] == json["name"]
    assert data["state"] == room_1.state
    assert data["explanation"] == json["explanation"]
    assert data["detail_of_role"] == json["detail_of_role"]
    assert data["created_at"] == room_1.created_at.strftime("%Y-%m-%dT%H:%M:%S.%f")
    assert data["updated_at"] == room_1.updated_at.strftime("%Y-%m-%dT%H:%M:%S.%f")
    assert data["users"][0]["id"] == user_1.id
    assert data["users"][0]["alias"] == user_1.alias


# TODO enter_room()のテスト
def test_enter_room(session: Session, client: TestClient):
    room_1 = Room(name="room_1")
    session.add(room_1)
    session.commit()
    user_1 = User(name="Tommy", session_token=str(uuid4()), alias="Rustyman")
    session.add(user_1)
    session.commit()

    params = {"room_id": room_1.id}
    client.cookies.set("session_token", user_1.session_token)
    response = client.post(f"/rooms/entrance/", params=params)
    data = response.json()
    print(data)
    assert response.status_code == 200
    assert data["name"] == room_1.name
    assert data["state"] == room_1.state
    assert data["detail_of_role"] == room_1.detail_of_role
    assert data["created_at"] == room_1.created_at.strftime("%Y-%m-%dT%H:%M:%S.%f")
    assert data["updated_at"] == room_1.updated_at.strftime("%Y-%m-%dT%H:%M:%S.%f")
    assert data["users"][0]["id"] == user_1.id
    assert data["users"][0]["alias"] == user_1.alias


def test_center_room_incomplete(client: TestClient):
    # No name
    response = client.post("/rooms/entrance/")
    assert response.status_code == 422


def test_enter_room_invalid(session: Session, client: TestClient):
    room_1 = Room(name="room_1")
    room_2 = Room(name="room_2")
    session.add(room_1)
    session.add(room_2)
    session.commit()

    user_1 = User(
        name="Tommy", session_token=str(uuid4()), alias="Rustyman", room_id=room_1.id
    )
    session.add(user_1)
    session.commit()

    params = {"room_id": room_2.id}
    client.cookies.set("session_token", user_1.session_token)
    response = client.post(f"/rooms/entrance/", params=params)
    assert response.status_code == 409


# TODO exit_room()のテスト

# TODO read_messages()のテスト
# TODO create_message()のテスト
