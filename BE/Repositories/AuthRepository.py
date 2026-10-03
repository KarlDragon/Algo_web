
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from Models.Users import Base, User


# Tim file .env tai thu muc goc du an
BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"

load_dotenv(ENV_PATH)

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError(
        f"Khong tim thay DATABASE_URL trong file: {ENV_PATH}"
    )

engine = create_engine(
    DATABASE_URL,
    echo=True
)


class AuthRepository:

    def create_user_table(self):
        Base.metadata.create_all(engine)

    def add_user(self, username, hashPassword, email):
        with Session(engine) as session:

            user = User(
                username=username,
                hashPassword=hashPassword,
                email=email
            )

            session.add(user)

            try:
                session.commit()
                session.refresh(user)
                return user

            except IntegrityError:
                session.rollback()
                print("Loi: Username hoac Email da ton tai!")
                return None
