from sqlmodel import SQLModel, Field, Relationship, text
from typing import List, Optional, Dict
from datetime import datetime, timedelta
from uuid import uuid4
from enum import Enum


# Roleは会話の閲覧権限のスコープの指定、action配下の各エンドポイントの利用権限のスコープの指定を行う
class RoleBase:
    pass


class RoleWolf(RoleBase):
    pass


class RoleVillager(RoleBase):
    pass


RoleClassList = {"villager": RoleVillager, "wolf": RoleWolf}


# Room 👇
class RoomStateEnum(Enum):
    BEFOREGAME = "BeforeGame"
    FIRSTNIGHT = "FirstNight"
    SECONDMORNING = "SecondMorning"
    DAYTIME = "DayTime"
    SUNSET = "SunSet"
    NIGHT = "Night"
    MORNING = "Morning"
    AFTERGAME = "AfterGame"
    CLOSED = "Closed"


ROOMSTATETIME = {
    RoomStateEnum.BEFOREGAME.value: 30,
    RoomStateEnum.FIRSTNIGHT.value: 3,
    RoomStateEnum.SECONDMORNING.value: 0.25,
    RoomStateEnum.DAYTIME.value: 5,
    RoomStateEnum.SUNSET.value: 2,
    RoomStateEnum.NIGHT.value: 3,
    RoomStateEnum.MORNING.value: 0.25,
    RoomStateEnum.AFTERGAME.value: 5,
    RoomStateEnum.CLOSED.value: 5,  # test用に5(分)と置いている
}

ROOMSTATECYCLE = {
    RoomStateEnum.BEFOREGAME.value: RoomStateEnum.CLOSED.value,
    RoomStateEnum.FIRSTNIGHT.value: RoomStateEnum.SECONDMORNING.value,
    RoomStateEnum.SECONDMORNING.value: RoomStateEnum.DAYTIME.value,
    RoomStateEnum.DAYTIME.value: RoomStateEnum.SUNSET.value,
    RoomStateEnum.SUNSET.value: RoomStateEnum.NIGHT.value,
    RoomStateEnum.NIGHT.value: RoomStateEnum.MORNING.value,
    RoomStateEnum.MORNING.value: RoomStateEnum.DAYTIME.value,
    RoomStateEnum.AFTERGAME.value: RoomStateEnum.CLOSED.value,
    RoomStateEnum.CLOSED.value: None,
}


class RoomBase(SQLModel):
    name: str
    explanation: str | None


class Room(RoomBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    state: str | None = Field(
        default=str(RoomStateEnum.BEFOREGAME.value), nullable=False
    )
    detail_of_role: str | None = None
    created_at: datetime | None = Field(
        default_factory=lambda: datetime.now(), nullable=False
    )
    updated_at: datetime | None = Field(
        default_factory=lambda: datetime.now(),
        nullable=False,
        sa_column_kwargs={"onupdate": lambda: datetime.now()},
    )
    next_state_update_at: datetime | None = Field(
        default_factory=lambda: datetime.now() + timedelta(minutes=30), nullable=False
    )  # デフォルトでは部屋建てから30分後にゲームが始まっていないと村を閉じる。
    users: List["User"] | None = Relationship(back_populates="room")
    messages: List["Message"] | None = Relationship(back_populates="room")


class RoomPublic(RoomBase):
    id: int
    state: str | None
    detail_of_role: str | None
    created_at: datetime
    updated_at: datetime
    users: List["UserPublicWithoutName"] | None


class RoomCreate(RoomBase):
    pass


class RoomUpdate(SQLModel):
    name: str | None = None
    explanation: str | None = None
    detail_of_role: str | None = None


# Room 👆


# User 👇
class UserStateEnum(Enum):
    OUTOFPLAY = "OutOfPlay"
    ALIVE = "Alive"
    DEAD = "Dead"
    WATCHER = "Watcher"
    OUTSIDE = "OutSide"


class UserBase(SQLModel):
    alias: str | None = None
    pass


class User(UserBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str | None
    state: str = Field(default=str(UserStateEnum.OUTSIDE.value), nullable=False)
    role_key: str | None = None
    session_token: str | None = Field(
        default_factory=lambda: str(uuid4()), nullable=False, index=True
    )
    room: Room | None = Relationship(back_populates="users")
    room_id: int | None = Field(default=None, foreign_key="room.id")
    messages: List["Message"] | None = Relationship(back_populates="user")


class UserPublicWithoutName(UserBase):
    id: int
    state: str


class UserPublicWithName(UserPublicWithoutName):
    name: str
    state: str


class UserCreate(UserBase):
    name: str
    pass


class UserUpdate(SQLModel):
    name: str | None = None
    alias: str | None = None


# User 👆

# Message　👇


class MessageBase(SQLModel):
    content: str


class Message(MessageBase, table=True):
    id: int = Field(default=None, primary_key=True)
    room_id: int = Field(default=None, foreign_key="room.id")
    room: Room = Relationship(back_populates="messages")
    user_id: int = Field(default=None, foreign_key="user.id")
    user: User = Relationship(back_populates="messages")
    target_user: str | None = None
    target_group: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(), nullable=False)


class MessagePublic(MessageBase):
    id: int
    room_id: int
    room: RoomPublic
    user_id: int
    user: UserPublicWithoutName
    created_at: datetime
    target_user: str | None = None
    target_group: str | None = None


class MessageWolf(MessageBase):
    id: int
    room_id: int
    room: RoomPublic
    user_id: int
    user: UserPublicWithoutName
    created_at: datetime
    target_user: str | None = None
    target_group: str = "wolf"


class MessageCreate(MessageBase):
    content: str


class MessageUpdate(SQLModel):
    content: str | None = None


# Message 👆


# Role　👇
class Role:
    name: str
    role_group: "RoleGroup"
    role_type: "RoleType"


class Wolf(Role):
    name = "wolf"
    role_group = RoleGroupWolf()


# Role　👆


# RoleGroup　👇
class RoleGroup:
    name: str


class RoleGroupWolf(RoleGroup):
    name = "wolf"


# RoleGroup　👆
# RoleType　👇
class RoleType:
    name: str


# RoleType　👆
