import logging


def pytest_configure(config):
    logging.basicConfig(level=logging.INFO)


from fastapi import (
    Depends,
    FastAPI,
    Query,
    Cookie,
    Response,
    HTTPException,
    status,
    Request,
)
from sqlmodel import Field, Relationship, Session, SQLModel, create_engine, select
from database import engine
from models import (
    User,
    UserPublicWithName,
    UserCreate,
    UserPublicWithoutName,
    UserStateEnum,
    RoomPublic,
    RoomCreate,
    Room,
    RoomUpdate,
    RoomStateEnum,
    ROOMSTATECYCLE,
    Message,
    MessageCreate,
    MessagePublic,
)
from datetime import datetime, timedelta
from starlette.middleware.base import BaseHTTPMiddleware
from typing import List


# 時間経過による更新処理をここで行う
def update_by_time(session: Session):
    rooms: List[Room] = session.exec(select(Room)).all()

    for room in rooms:
        if room.next_state_update_at <= datetime.now():
            room.state = str(ROOMSTATECYCLE[room.state])
            room.next_state_update_at += timedelta(minutes=5)
            session.add(room)
    session.commit()
    return session


def get_session():
    with Session(engine) as session:
        update_by_time(session=session)
        yield session


app = FastAPI()


def get_user(
    session_token: str,
    session: Session,
):
    if session_token is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You have not created a user yet.",
        )
    user = session.exec(select(User).where(User.session_token == session_token)).one()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Your session_token is invalid.",
        )
    return user


@app.get("/time/")
def read_time(*, session: Session = Depends(get_session)):
    update_by_time(session=session)
    return {"time": str(datetime.now())}


@app.post("/users/", response_model=UserPublicWithName)
def create_user(
    *,
    response: Response,
    session: Session = Depends(get_session),
    user: UserCreate,
    session_token: str | None = Cookie(None),
):
    update_by_time(session=session)
    if session_token is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"You have alerady created a user .",
        )

    db_user = User.model_validate(user)
    response.set_cookie(key="session_token", value=db_user.session_token)

    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return db_user


@app.get("/users/", response_model=list[UserPublicWithoutName])
def read_users(
    *,
    session: Session = Depends(get_session),
    offset: int = 0,
    limit: int = Query(default=100, le=100),
    session_token: str = Cookie(None),
):
    update_by_time(session=session)
    user = get_user(session_token, session)
    users = session.exec(
        select(User).where(User.room_id == user.room_id).offset(offset).limit(limit)
    ).all()
    return users


@app.get("/me/", response_model=UserPublicWithName)
def read_my_information(
    *,
    session: Session = Depends(get_session),
    session_token: str = Cookie(None),
):
    update_by_time(session=session)
    user = get_user(session_token, session)
    return user


@app.post("/rooms/", response_model=RoomPublic)
def create_room(*, session: Session = Depends(get_session), room: RoomCreate):
    update_by_time(session=session)
    db_room = Room.model_validate(room)
    session.add(db_room)
    session.commit()
    session.refresh(db_room)
    return db_room


@app.get("/rooms/", response_model=list[RoomPublic])
def read_rooms(
    *,
    session: Session = Depends(get_session),
    offset: int = 0,
    limit: int = Query(default=100, le=100),
):
    update_by_time(session=session)
    rooms = session.exec(select(Room).offset(offset).limit(limit)).all()
    return rooms


@app.patch("/rooms/{room_id}/settings/", response_model=RoomPublic)
def update_rooms(
    *,
    session: Session = Depends(get_session),
    session_token: str = Cookie(None),
    room_id: int,
    room: RoomUpdate,
):
    update_by_time(session=session)
    user = get_user(session_token, session)
    if user.room_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"You have not entered a room.",
        )
    if user.room_id != room_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You can not update the room setting that you are not in.",
        )
    db_room = session.exec(select(Room).where(Room.id == room_id)).one()
    room_data = room.model_dump(exclude_unset=True)

    for key, value in room_data.items():
        setattr(db_room, key, value)

    session.add(db_room)
    session.commit()
    session.refresh(db_room)
    print(db_room)
    return db_room


@app.post("/rooms/entrance/", response_model=RoomPublic)
def enter_room(
    *,
    session: Session = Depends(get_session),
    session_token: str = Cookie(None),
    room_id: int,
    isWatcher: bool = False,
):
    update_by_time(session=session)
    db_user = get_user(session_token, session)
    if db_user.room is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"You have entered a room.",
        )
    db_user.room_id = room_id
    if isWatcher:
        db_user.state = str(UserStateEnum.WATCHER.value)
    else:
        room = session.exec(select(Room).where(Room.id == db_user.room_id)).one()
        if room.state == str(RoomStateEnum.CLOSED.value):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This room is closed.",
            )
        elif room.state == str(RoomStateEnum.BEFOREGAME.value):
            db_user.state = str(UserStateEnum.OUTOFPLAY.value)
        elif room.state == str(RoomStateEnum.AFTERGAME.value):
            db_user.state = str(UserStateEnum.OUTOFPLAY.value)
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"The game has started. You can only enter the room as a watcher.",
            )
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return db_user.room


@app.post("/rooms/exit/", response_model=UserPublicWithName)
def exit_room(
    *,
    session: Session = Depends(get_session),
    session_token: str = Cookie(None),
):
    update_by_time(session=session)
    db_user = get_user(session_token, session)
    if db_user.room is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"You have not entered a room.",
        )
    db_user.room_id = None
    db_user.state = str(UserStateEnum.OUTSIDE.value)
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return db_user


@app.post("/rooms/{room_id}/game/start/", response_model=RoomPublic)
def game_start(
    *,
    session: Session = Depends(get_session),
    session_token: str = Cookie(None),
    room_id: int,
):
    update_by_time(session=session)
    user = get_user(session_token=session_token, session=session)
    if user.room_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"You have not entered a room.",
        )
    if user.room_id != room_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You can not update the room setting that you are not in.",
        )
    db_room = session.exec(select(Room).where(Room.id == room_id)).one()
    if db_room.state != str(RoomStateEnum.BEFOREGAME.value):
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail=f"This room is not before a game.",
        )
    db_room.state = str(RoomStateEnum.FIRSTNIGHT.value)
    session.add(db_room)
    for db_user in db_room.users:
        if db_user.state == str(UserStateEnum.WATCHER.value):
            continue
        db_user.state = str(UserStateEnum.ALIVE.value)
        session.add(db_user)
    session.commit()
    return db_room


@app.post("/rooms/{room_id}/game/end/", response_model=RoomPublic)
def game_end(
    *,
    session: Session = Depends(get_session),
    session_token: str = Cookie(None),
    room_id: int,
):
    update_by_time(session=session)
    user = get_user(session_token=session_token, session=session)
    if user.room_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"You have not entered a room.",
        )
    if user.room_id != room_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You can not update the room setting that you are not in.",
        )
    db_room = session.exec(select(Room).where(Room.id == room_id)).one()
    if db_room.state != (
        str(RoomStateEnum.DAYTIME.value)
        or str(RoomStateEnum.FIRSTNIGHT.value)
        or str(RoomStateEnum.NIGHT.value)
        or str(RoomStateEnum.SCONDMORNING.value)
        or str(RoomStateEnum.SUNSET.value)
        or str(RoomStateEnum.MORNING.value)
    ):
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail=f"This room is not in Game.",
        )
    db_room.state = str(RoomStateEnum.AFTERGAME.value)
    for db_user in db_room.users:
        if db_user.state == str(UserStateEnum.WATCHER.value):
            continue
        db_user.state = str(UserStateEnum.OUTOFPLAY.value)
        session.add(db_user)
    session.add(db_room)
    session.commit()
    return db_room


@app.post("/rooms/{room_id}/close/")
def close_room(
    *,
    session: Session = Depends(get_session),
    session_token: str = Cookie(None),
    room_id: int,
):
    update_by_time(session=session)
    user = get_user(session_token=session_token, session=session)
    if user.room_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"You have not entered a room.",
        )
    if user.room_id != room_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You can not update the room setting that you are not in.",
        )
    db_room = session.exec(select(Room).where(Room.id == room_id)).one()
    db_room.state = str(RoomStateEnum.CLOSED.value)
    for db_user in db_room.users:
        db_user.room_id = None
        db_user.state = str(UserStateEnum.OUTSIDE.value)
        session.add(db_user)
    session.add(db_room)
    session.commit
    return {"state": "ok"}


# TODO target_groupをroomのstateとuserのroleによって動的に決定する
@app.get("/messages/", response_model=list[MessagePublic])
def read_messages(
    *,
    session: Session = Depends(get_session),
    offset: int = 0,
    limit: int = Query(default=100, le=100),
    session_token: str = Cookie(None),
    target_group: str | None = None,
):
    update_by_time(session=session)
    user = get_user(session_token, session)
    room = session.exec(select(Room).where(Room.id == user.room_id)).one()
    if room is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"You have not entered a room.",
        )
    messages = session.exec(
        select(Message)
        .where(Message.room_id == room.id and Message.target_group == target_group)
        .offset(offset)
        .limit(limit)
    ).all()
    return messages


@app.post("/messages/", response_model=MessagePublic)
def create_message(
    *,
    message: MessageCreate,
    session: Session = Depends(get_session),
    session_token: str = Cookie(None),
):
    update_by_time(session=session)
    user = get_user(session_token, session)
    if user.room is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"You have not entered a room.",
        )
    db_message = Message.model_validate(message)
    db_message.room_id = user.room_id
    db_message.user_id = user.id
    session.add(db_message)
    session.commit()
    session.refresh(db_message)
    return db_message
