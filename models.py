from sqlmodel import SQLModel, Field, Relationship
from typing import List, Optional
from datetime import datetime


class Room(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    users: List["User"] = Relationship(back_populates="room")


class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    username: str
    room_id: int | None = Field(default=None, foreign_key="room.id")
    room: Room | None = Relationship(back_populates="users")


class Message(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    room_id: int
    user_id: int
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
