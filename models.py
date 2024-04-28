from sqlmodel import SQLModel, Field, Relationship, text
from typing import List, Optional
from datetime import datetime, timedelta


# Room　👇
class RoomBase(SQLModel):
    name: str
    explanation: str | None


class Room(RoomBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    state: str | None = None
    detail_of_role: str | None = None
    created_at: datetime | None = Field(default_factory=datetime.now, nullable=False)
    updated_at: datetime | None = Field(
        default_factory=datetime.now,
        nullable=False,
        sa_column_kwargs={"onupdate": datetime.now},
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
class UserBase(SQLModel):
    alias: str | None = None
    pass


class User(UserBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str | None
    state: str | None = None
    role: str | None = None
    group: str | None = None
    session_token: str | None = Field(default=None, index=True)
    room: Room | None = Relationship(back_populates="users")
    room_id: int | None = Field(default=None, foreign_key="room.id")
    messages: List["Message"] | None = Relationship(back_populates="user")


class UserPublicWithoutName(UserBase):
    id: int


class UserPublicWithName(UserPublicWithoutName):
    name: str


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
    created_at: datetime = Field(default_factory=datetime.now, nullable=False)


class MessagePublic(MessageBase):
    id: int
    room_id: int
    room: RoomPublic
    user_id: int
    user: UserPublicWithoutName
    created_at: datetime
    target_user: str | None = None
    target_group: str | None = None


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
