from pwdlib import PasswordHash
from sqlalchemy.orm import Session

from Repositories.AuthRepository import AuthRepository


class LoginService:
    def __init__(self, session: Session):
        self.auth_repository = AuthRepository(session)
        self.password_hash = PasswordHash.recommended()

    def verify_password(self, password, hashed_password):
        return self.password_hash.verify(
            password,
            hashed_password
        )

    def login_user(self, login, password):
        if login == "" or password == "":
            return None

        user = self.auth_repository.get_user_by_username_or_email(
            login
        )

        if user is None:
            return None

        if not self.verify_password(
            password,
            user.hashPassword
        ):
            return None

        return user