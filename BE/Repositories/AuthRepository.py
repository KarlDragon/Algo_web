import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from Models.Base import Base
from Models.Users import User


class AuthRepository:

    def __init__(self):
        env_path = Path(__file__).resolve().parents[1] / ".env"

        load_dotenv(env_path)

        database_url = os.getenv("DATABASE_URL")

        if database_url is None:
            raise ValueError(
                "DATABASE_URL khong ton tai trong file .env"
            )

        self.engine = create_engine(
            database_url,
            echo=True
        )

    def create_user_table(self):
        Base.metadata.create_all(self.engine)

    def get_user_by_username(self, username):
        with Session(self.engine) as session:
            statement = select(User).where(
                User.username == username
            )

            user = session.scalar(statement)

            return user

    def get_user_by_email(self, email):
        with Session(self.engine) as session:
            statement = select(User).where(
                User.email == email
            )

            user = session.scalar(statement)

            return user

    def add_user(self, username, hashPassword, email):
        with Session(self.engine) as session:
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

                return None