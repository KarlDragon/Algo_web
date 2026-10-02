from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from Models.Users import Base, User


engine = create_engine(
    "sqlite:///users.db",
    echo=True
)


def create_user_table():
    Base.metadata.create_all(engine)


def add_user(username, hashPassword, email):
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
            return None
