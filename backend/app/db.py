import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base

DEFAULT_DATABASE_URL = "sqlite:///./foodmap.db"


def make_engine(url: str | None = None):
    url = url or os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    # pool_pre_ping: a connection that has gone stale while idle in the pool
    # (an SSH tunnel or Postgres itself closing it after inactivity) would
    # otherwise hang indefinitely on first use instead of failing fast.
    return create_engine(url, connect_args=connect_args, pool_pre_ping=True)


def init_db(engine) -> None:
    Base.metadata.create_all(engine)


def make_session_factory(engine):
    return sessionmaker(bind=engine)
