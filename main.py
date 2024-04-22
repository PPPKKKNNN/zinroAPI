from fastapi import Depends, FastAPI, HTTPException, Query
from sqlmodel import Field, Relationship, Session, SQLModel, create_engine, select
from database import engine, create_db_and_tables
from models import User, UserPublic, UserCreate


def get_session():
    with Session(engine) as session:
        yield session


app = FastAPI()


@app.post("/users/", response_model=UserPublic)
def create_user(*, session: Session = Depends(get_session), user: UserCreate):
    print(user)
    db_user = User.model_validate(user)
    print(db_user)
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return db_user


@app.get("/users/", response_model=list[UserPublic])
def read_users(
    *,
    session: Session = Depends(get_session),
    offset: int = 0,
    limit: int = Query(default=100, le=100),
):
    users = session.exec(select(User).offset(offset).limit(limit)).all()
    return users
