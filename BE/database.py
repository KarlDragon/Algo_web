import os
from collections.abc import Iterator
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

database_url = os.getenv("DATABASE_URL")
if not database_url:
    raise ValueError("DATABASE_URL khong ton tai trong file .env")

echo_sql = os.getenv("SQLALCHEMY_ECHO", "").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}

engine = create_engine(database_url, echo=echo_sql)
SessionLocal = sessionmaker(bind=engine)


def get_db() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session
