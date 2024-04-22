from sqlmodel import SQLModel, create_engine, Session
from secret import password

url = f"postgresql://postgres:{password}@localhost:5432/zinrodb"
connect_args = {"check_same_thread": False}
engine = create_engine(url, echo=True, connect_args=connect_args)


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)
