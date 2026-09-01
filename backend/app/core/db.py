import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.config import get_settings
from app.models.entities import Base


def make_engine():
    return create_engine(
        os.environ.get("DATABASE_URL") or get_settings().database_url,
        pool_pre_ping=True,
    )


engine = make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
