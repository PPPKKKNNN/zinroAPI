from fastapi import FastAPI, Depends, HTTPException, Cookie
from fastapi.responses import HTMLResponse
from sqlmodel import Session, select
from models import Room, User
from database import engine

app = FastAPI()


def get_session():
    with Session(engine) as session:
        yield session


@app.post("/rooms/")
def create_room(room: Room, db: Session = Depends(get_session)):
    db.add(room)
    db.commit()
    db.refresh(room)
    return room


@app.get("/rooms/")
def read_rooms(db: Session = Depends(get_session)):
    rooms = db.exec(select(Room)).all()
    return rooms


from fastapi.security import OAuth2PasswordBearer

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


@app.post("/users/login")
def login(user: User, response: HTMLResponse, db: Session = Depends(get_session)):
    db_user = db.exec(select(User).where(User.username == user.username)).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    response.set_cookie(key="session", value=str(user.id), httponly=True)
    return {"message": "User logged in"}


@app.get("/users/me")
def read_users_me(session: str = Cookie(None)):
    return {"session": session}
