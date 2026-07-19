from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base
import os

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./revoice.db")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
Base = declarative_base()


def create_tables():
    Base.metadata.create_all(bind=engine)
