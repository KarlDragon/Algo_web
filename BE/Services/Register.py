import re

from pwdlib import PasswordHash
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from Repositories.AuthRepository import AuthRepository


class RegisterService:

    def __init__(self, session: Session):
        self.session = session
        self.auth_repository = AuthRepository(session)
        self.password_hash = PasswordHash.recommended()

    def check_username(self, username):
        if username == "":
            print("Username khong duoc rong!")
            return False

        if len(username) > 50:
            print("Username khong duoc qua 50 ky tu!")
            return False

        if not re.search(r"[A-Za-z]", username):
            print("Username phai co it nhat 1 chu cai!")
            return False

        if not re.search(r"[0-9]", username):
            print("Username phai co it nhat 1 chu so!")
            return False

        return True

    def check_password(self, password):
        if password == "":
            print("Password khong duoc rong!")
            return False

        if len(password) < 8:
            print("Password phai co it nhat 8 ky tu!")
            return False

        if len(password) > 64:
            print("Password khong duoc qua 64 ky tu!")
            return False

        if not re.search(r"[A-Z]", password):
            print("Password phai co it nhat 1 chu cai in hoa!")
            return False

        if not re.search(r"[0-9]", password):
            print("Password phai co it nhat 1 chu so!")
            return False

        if not re.search(r"[^A-Za-z0-9]", password):
            print("Password phai co it nhat 1 ky tu dac biet!")
            return False

        return True

    def check_email(self, email):
        if email == "":
            print("Email khong duoc rong!")
            return False

        if len(email) > 100:
            print("Email khong duoc qua 100 ky tu!")
            return False

        email_pattern = (
            r"^[A-Za-z0-9._%+-]+@"
            r"[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"
        )

        if not re.match(email_pattern, email):
            print("Email khong hop le!")
            return False

        return True

    def hash_password(self, password):
        return self.password_hash.hash(password)

    def register_user(self, username, password, email):
        if not self.check_username(username):
            return None

        if not self.check_password(password):
            return None

        if not self.check_email(email):
            return None

        existing_username = (
            self.auth_repository.get_user_by_username(username)
        )

        if existing_username is not None:
            print("Username da ton tai!")
            return None

        existing_email = (
            self.auth_repository.get_user_by_email(email)
        )

        if existing_email is not None:
            print("Email da ton tai!")
            return None

        hashed_password = self.hash_password(password)

        user = self.auth_repository.add_user(
            username,
            hashed_password,
            email
        )

        if user is None:
            return None

        try:
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            return None

        return user