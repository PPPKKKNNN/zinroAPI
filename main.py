from fastapi import Depends, FastAPI, Query, Cookie, Response, HTTPException, status
from sqlmodel import Field, Relationship, Session, SQLModel, create_engine, select
from database import engine
from models import (
    User,
    UserPublicWithName,
    UserCreate,
    UserPublicWithoutName,
    RoomPublic,
    RoomCreate,
    Room,
    Message,
    MessageCreate,
    MessagePublic,
    RoomUpdate,
)
from uuid import uuid4
from datetime import datetime


def get_session():
    with Session(engine) as session:
        yield session


def get_user(
    session_token: str | None,
    session: Session,
):
    if session_token is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"You have not created a user yet.",
        )
    user = session.exec(select(User).where(User.session_token == session_token)).one()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Your session_token is invalid.",
        )
    return user


app = FastAPI()


@app.post("/users/", response_model=UserPublicWithName)
def create_user(
    *,
    response: Response,
    session: Session = Depends(get_session),
    user: UserCreate,
    session_token: str | None = Cookie(None),
):
    if session_token is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"You have alerady created a user .",
        )

    db_user = User.model_validate(user)
    # pytestで使うsqliteがuui型を使えないので文字列にしている
    db_user.session_token = str(uuid4())
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
    session_token: str | None = Cookie(None),
):
    print(f"sessionトークンは{session_token}")
    user = get_user(session_token, session)
    print(f"userは{user}")
    users = session.exec(
        select(User).where(User.room_id == user.room_id).offset(offset).limit(limit)
    ).all()
    return users


@app.get("/me/", response_model=UserPublicWithName)
def read_my_information(
    *,
    session: Session = Depends(get_session),
    session_token: str | None = Cookie(None),
):
    user = get_user(session_token, session)
    return user


@app.post("/rooms/", response_model=RoomPublic)
def create_room(*, session: Session = Depends(get_session), room: RoomCreate):
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
    rooms = session.exec(select(Room).offset(offset).limit(limit)).all()
    return rooms


@app.patch(
    "/rooms/",
)
def update_rooms(
    *,
    session: Session = Depends(get_session),
    session_token: str | None = Cookie(None),
    room: RoomUpdate,
):
    user = get_user(session_token, session)
    if user.room_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"You have not entered a room.",
        )
    db_room = session.exec(select(Room).where(Room.id == user.room_id)).one()
    room_data = room.model_dump(exclude_unset=True)

    for key, value in room_data.items():
        setattr(db_room, key, value)

    session.add(db_room)
    session.commit()
    session.refresh(db_room)
    return {"detail": "Your room have updated."}


@app.post("/rooms/entrance/")
def enter_room(
    *,
    session: Session = Depends(get_session),
    session_token: str | None = Cookie(None),
    room_id: int,
):
    db_user = get_user(session_token, session)
    if db_user.room is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"You have entered a room.",
        )
    db_user.room_id = room_id

    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return {"detail": "You have enterd."}


@app.post("/rooms/exit/")
def exit_room(
    *,
    session: Session = Depends(get_session),
    session_token: str | None = Cookie(None),
):
    db_user = get_user(session_token, session)
    if db_user.room is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"You have not entered a room.",
        )
    db_user.room_id = None
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return {"detail": "You have exited."}


# TODO recipient_groupをroomのstateとuserのroleによって動的に決定する
@app.get("/messages/", response_model=list[MessagePublic])
def read_messages(
    *,
    session: Session = Depends(get_session),
    offset: int = 0,
    limit: int = Query(default=100, le=100),
    session_token: str | None = Cookie(None),
    target_group: str | None = None,
):
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
    session_token: str | None = Cookie(None),
):
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
