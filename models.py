from sqlmodel import SQLModel, Field, Relationship
from typing import List, Optional
from datetime import datetime


class RoomBase(SQLModel):
    name: str


class Room(RoomBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    users: List["User"] | None = Relationship(back_populates="room")


class RoomPublic(RoomBase):
    id: int


class RoomCreate(RoomBase):
    pass


class RoomUpdate(SQLModel):
    name: int | None = None


class UserBase(SQLModel):
    name: str


class User(UserBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    room: Room | None = Relationship(back_populates="users")
    room_id: int | None = Field(default=None, foreign_key="room.id")


class UserPublic(UserBase):
    id: int
    room_id: int | None


class UserCreate(UserBase):
    pass


class UseUpdate(SQLModel):
    name: int | None = None
    room: Room | None = Relationship(back_populates="users")


class Message(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    room_id: int
    user_id: int
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)
