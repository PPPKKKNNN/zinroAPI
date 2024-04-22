from fastapi import Depends, FastAPI, HTTPException, Query
from sqlmodel import Field, Relationship, Session, SQLModel, create_engine, select
from database import engine, create_db_and_tables
from models import *


def get_session():
    with Session(engine) as session:
        yield session


app = FastAPI()
