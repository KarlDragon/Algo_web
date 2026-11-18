from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from Models.Users import User


class AuthRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_user_by_id(self, user_id: int) -> User | None:
        return self.session.get(User, user_id)

    def get_user_by_username(self, username: str) -> User | None:
        return self.session.scalar(select(User).where(User.username == username))

    def get_user_by_email(self, email: str) -> User | None:
        return self.session.scalar(
            select(User).where(func.lower(User.email) == email.strip().lower())
        )

    def get_user_by_username_or_email(self, login: str) -> User | None:
        if "@" in login:
            return self.get_user_by_email(login)
        return self.get_user_by_username(login)

    def add_user(self, username: str, hashPassword: str, email: str) -> User | None:
        user = User(username=username, hashPassword=hashPassword, email=email, role="USER")
        self.session.add(user)
        try:
            self.session.flush()
            self.session.refresh(user)
            return user
        except IntegrityError:
            self.session.rollback()
            return None
