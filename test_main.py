import logging


def pytest_configure(config):
    logging.basicConfig(level=logging.INFO)


import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

from main import app, get_session, update_by_time
from models import User, Room, UserStateEnum, RoomStateEnum
from uuid import uuid4

from freezegun import freeze_time
import datetime

# TODO 部屋主以外が部屋を消したりゲームを終了したりできないようにする。


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


app.dependency_overrides[get_session] = session_fixture


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
    user_1 = User(name="Deadpond", alias="Dive Wilson")
    user_2 = User(name="Rusty-Man")
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
    user_1 = User(name="Deadpond", alias="Dive Wilson")
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
    response = client.get(f"/me/")
    assert response.status_code == 403


def test_create_room(session: Session, client: TestClient):
    user_1 = User(name="Deadpond", alias="Dive Wilson")
    session.add(user_1)
    session.commit()

    client.cookies.set("session_token", user_1.session_token)
    response = client.post(
        "/rooms/",
        json={"name": "room_1", "explanation": "This is explanationnof room_1."},
    )
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == "room_1"
    assert data["explanation"] == "This is explanationnof room_1."


def test_create_room_incomplete(session: Session, client: TestClient):
    user_1 = User(name="Deadpond", alias="Dive Wilson")
    session.add(user_1)
    session.commit()

    client.cookies.set("session_token", user_1.session_token)
    response = client.post(
        "/rooms/", json={"explanation": "This is explanationnof room_1."}
    )
    assert response.status_code == 422


def test_create_room_invalid(session: Session, client: TestClient):
    # alias has an invalid type
    user_1 = User(name="Deadpond", alias="Dive Wilson")
    session.add(user_1)
    session.commit()

    client.cookies.set("session_token", user_1.session_token)
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

    user_1 = User(name="Tommy", room_id=room_2.id, alias="Rustyman")
    session.add(user_1)
    session.commit()

    user_2 = User(name="Deadpond", alias="Dive Wilson")
    session.add(user_2)
    session.commit()

    client.cookies.set("session_token", user_2.session_token)
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
    assert data[0]["users"][0]["id"] == user_1.id
    assert data[0]["users"][0]["alias"] == user_1.alias

    # 説明文がある場合のテスト
    assert data[1]["explanation"] == room_3.explanation


def test_update_room(session: Session, client: TestClient):
    room_1 = Room(name="room_1")
    session.add(room_1)
    session.commit()
    user_1 = User(name="Tommy", room_id=room_1.id, alias="Rustyman")
    session.add(user_1)
    session.commit()

    json = {
        "name": "Hazbin Hotel",
        "explanation": "The best hotel in Hell",
        "detail_of_role": "devils",
    }
    client.cookies.set("session_token", user_1.session_token)
    response = client.patch(
        f"/rooms/{room_1.id}/settings/",
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


def test_update_room_NO_room_id(session: Session, client: TestClient):
    room_1 = Room(name="room_1")
    session.add(room_1)
    session.commit()
    user_1 = User(name="Tommy", alias="Rustyman")
    session.add(user_1)
    session.commit()

    json = {
        "name": "Hazbin Hotel",
        "explanation": "The best hotel in Hell",
        "detail_of_role": "devils",
    }
    client.cookies.set("session_token", user_1.session_token)
    response = client.patch(
        f"/rooms/{room_1.id}/settings/",
        json=json,
    )
    assert response.status_code == 404


def test_update_room_invalid_room_id(session: Session, client: TestClient):
    room_1 = Room(name="room_1")
    room_2 = Room(name="room_2")
    session.add(room_1)
    session.add(room_2)
    session.commit()
    user_1 = User(name="Tommy", alias="Rustyman", room_id=room_1.id)
    session.add(user_1)
    session.commit()

    json = {
        "name": "Hazbin Hotel",
        "explanation": "The best hotel in Hell",
        "detail_of_role": "devils",
    }
    client.cookies.set("session_token", user_1.session_token)
    response = client.patch(
        f"/rooms/{room_2.id}/settings/",
        json=json,
    )
    assert response.status_code == 403


def test_enter_room(session: Session, client: TestClient):
    room_1 = Room(name="room_1")
    session.add(room_1)
    session.commit()
    user_1 = User(name="Tommy", alias="Rustyman")
    session.add(user_1)
    session.commit()
    params = {"room_id": room_1.id}
    client.cookies.set("session_token", user_1.session_token)
    response = client.post(f"/rooms/entrance/", params=params)
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == room_1.name
    assert data["state"] == room_1.state
    assert data["detail_of_role"] == room_1.detail_of_role
    assert data["created_at"] == room_1.created_at.strftime("%Y-%m-%dT%H:%M:%S.%f")
    assert data["updated_at"] == room_1.updated_at.strftime("%Y-%m-%dT%H:%M:%S.%f")
    assert data["users"][0]["id"] == user_1.id
    assert data["users"][0]["alias"] == user_1.alias


def test_enter_room_incomplete(session: Session, client: TestClient):
    user_1 = User(name="Deadpond", alias="Dive Wilson")
    session.add(user_1)
    session.commit()
    client.cookies.set("session_token", user_1.session_token)
    response = client.post("/rooms/entrance/")
    assert response.status_code == 422


def test_enter_room_invalid(session: Session, client: TestClient):
    room_1 = Room(name="room_1")
    room_2 = Room(name="room_2")
    session.add(room_1)
    session.add(room_2)
    session.commit()

    user_1 = User(name="Tommy", alias="Rustyman", room_id=room_1.id)
    session.add(user_1)
    session.commit()

    params = {"room_id": room_2.id}
    client.cookies.set("session_token", user_1.session_token)
    response = client.post(f"/rooms/entrance/", params=params)
    assert response.status_code == 409


def test_exit_room(session: Session, client: TestClient):
    room_1 = Room(name="room_1")
    session.add(room_1)
    session.commit()
    user_1 = User(
        name="Tommy",
        room_id=room_1.id,
        state=str(UserStateEnum.OUTOFPLAY.value),
        alias="Rustyman",
    )
    session.add(user_1)
    session.commit()

    client.cookies.set("session_token", user_1.session_token)
    response = client.post(f"/rooms/exit/")
    data = response.json()
    assert response.status_code == 200
    assert data["state"] == str(UserStateEnum.OUTSIDE.value)


def test_game_start(session: Session, client: TestClient):
    room_1 = Room(name="room_1")
    session.add(room_1)
    session.commit()
    user_1 = User(
        name="Tommy",
        room_id=room_1.id,
        state=str(UserStateEnum.OUTOFPLAY.value),
        alias="Rustyman",
    )
    user_2 = User(
        name="Romance",
        room_id=room_1.id,
        state=str(UserStateEnum.OUTOFPLAY.value),
        alias="Shifter",
    )
    user_3 = User(
        name="Steffany",
        room_id=room_1.id,
        state=str(UserStateEnum.WATCHER.value),
        alias="CaptainAfrica",
    )
    user_4 = User(
        name="Ronin",
        room_id=None,
        state=str(UserStateEnum.OUTSIDE.value),
        alias="ForkEye",
    )
    session.add(user_1)
    session.add(user_2)
    session.add(user_3)
    session.add(user_4)
    session.commit()

    client.cookies.set("session_token", user_1.session_token)
    response = client.post(f"/rooms/{room_1.id}/game/start/")
    data = response.json()
    assert response.status_code == 200
    assert data["state"] == str(RoomStateEnum.FIRSTNIGHT.value)
    assert room_1.state == str(RoomStateEnum.FIRSTNIGHT.value)
    assert user_1.state == str(UserStateEnum.ALIVE.value)
    assert user_2.state == str(UserStateEnum.ALIVE.value)
    assert user_3.state == str(UserStateEnum.WATCHER.value)
    assert user_4.state == str(UserStateEnum.OUTSIDE.value)


def test_game_start_invalid(session: Session, client: TestClient):
    room_1 = Room(name="room_1", state=str(RoomStateEnum.DAYTIME.value))
    session.add(room_1)
    session.commit()
    user_1 = User(
        name="Tommy",
        room_id=room_1.id,
        state=str(UserStateEnum.ALIVE.value),
        alias="Rustyman",
    )
    session.add(user_1)
    session.commit()

    client.cookies.set("session_token", user_1.session_token)
    response = client.post(f"/rooms/{room_1.id}/game/start/")
    assert response.status_code == 412


# TODO game_end()のテスト
def test_game_end(session: Session, client: TestClient):
    room_1 = Room(name="room_1", state=str(RoomStateEnum.DAYTIME.value))
    session.add(room_1)
    session.commit()
    user_1 = User(
        name="Tommy",
        room_id=room_1.id,
        state=str(UserStateEnum.ALIVE.value),
        alias="Rustyman",
    )
    user_2 = User(
        name="Romance",
        room_id=room_1.id,
        state=str(UserStateEnum.ALIVE.value),
        alias="Shifter",
    )
    user_3 = User(
        name="Steffany",
        room_id=room_1.id,
        state=str(UserStateEnum.WATCHER.value),
        alias="CaptainAfrica",
    )
    session.add(user_1)
    session.add(user_2)
    session.add(user_3)
    session.commit()

    client.cookies.set("session_token", user_1.session_token)
    response = client.post(f"/rooms/{room_1.id}/game/end/")
    data = response.json()
    assert response.status_code == 200
    assert data["state"] == str(RoomStateEnum.AFTERGAME.value)
    assert user_1.state == str(UserStateEnum.OUTOFPLAY.value)
    assert user_2.state == str(UserStateEnum.OUTOFPLAY.value)
    assert user_3.state == str(UserStateEnum.WATCHER.value)


def test_game_end_invalid(session: Session, client: TestClient):
    room_1 = Room(name="room_1", state=str(RoomStateEnum.AFTERGAME.value))
    session.add(room_1)
    session.commit()
    user_1 = User(
        name="Tommy",
        room_id=room_1.id,
        state=str(UserStateEnum.OUTOFPLAY.value),
        alias="Rustyman",
    )
    session.add(user_1)
    session.commit()

    client.cookies.set("session_token", user_1.session_token)
    response = client.post(f"/rooms/{room_1.id}/game/end/")

    assert response.status_code == 412


def test_room_close(session: Session, client: TestClient):
    room_1 = Room(name="room_1", state=str(RoomStateEnum.AFTERGAME.value))
    session.add(room_1)
    session.commit()
    user_1 = User(
        name="Tommy",
        room_id=room_1.id,
        state=str(UserStateEnum.OUTOFPLAY.value),
        alias="Rustyman",
    )
    user_2 = User(
        name="Romance",
        room_id=room_1.id,
        state=str(UserStateEnum.OUTOFPLAY.value),
        alias="Shifter",
    )
    user_3 = User(
        name="Steffany",
        room_id=room_1.id,
        state=str(UserStateEnum.WATCHER.value),
        alias="CaptainAfrica",
    )
    session.add(user_1)
    session.add(user_2)
    session.add(user_3)
    session.commit()

    client.cookies.set("session_token", user_1.session_token)
    response = client.post(f"/rooms/{room_1.id}/close/")
    data = response.json()
    assert response.status_code == 200
    assert room_1.state == str(RoomStateEnum.CLOSED.value)
    assert user_1.state == str(UserStateEnum.OUTSIDE.value)
    assert user_2.state == str(UserStateEnum.OUTSIDE.value)
    assert user_3.state == str(UserStateEnum.OUTSIDE.value)
    assert user_1.room_id == None
    assert user_2.room_id == None
    assert user_3.room_id == None


# TODO AppMiddlewareのテスト
@freeze_time("2023-04-01")
def test_time_forward(session: Session, client: TestClient):
    room_1 = Room(name="room_1")
    session.add(room_1)
    session.commit
    with freeze_time(datetime.datetime.now() + datetime.timedelta(minutes=31)):
        client.get("/rooms/")
        assert room_1.state == str(RoomStateEnum.CLOSED.value)


# TODO read_messages()のテスト

# TODO create_message()のテスト
