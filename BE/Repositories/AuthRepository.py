from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from Models.Users import User


class AuthRepository:

    def __init__(self, session: Session):
        self.session = session

    def get_user_by_username(self, username):
        statement = select(User).where(
            User.username == username
        )

        return self.session.scalar(statement)

    def get_user_by_email(self, email):
        statement = select(User).where(
            User.email == email
        )

        return self.session.scalar(statement)

    def add_user(self, username, hashPassword, email):
        user = User(
            username=username,
            hashPassword=hashPassword,
            email=email
        )
        self.session.add(user)

        try:
            self.session.flush()
            self.session.refresh(user)
            return user
        except IntegrityError:
            self.session.rollback()
            return None