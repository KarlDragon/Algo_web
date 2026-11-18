import re

from pwdlib import PasswordHash
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from Repositories.AuthRepository import AuthRepository


class RegistrationError(Exception):
    """Lỗi nghiệp vụ; Controller chuyển thành HTTP 400 hoặc HTTP 409."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


class RegisterService:
    def __init__(self, session: Session):
        self.session = session
        self.auth_repository = AuthRepository(session)
        self.password_hash = PasswordHash.recommended()

    def check_username(self, username: str) -> bool:
        if not username:
            raise RegistrationError("Tên đăng nhập không được để trống")

        if not 3 <= len(username) <= 50:
            raise RegistrationError("Tên đăng nhập phải có từ 3 đến 50 ký tự")

        if re.fullmatch(r"[A-Za-z0-9_]+", username) is None:
            raise RegistrationError(
                "Tên đăng nhập chỉ được chứa chữ cái không dấu, số và dấu gạch dưới"
            )

        if re.search(r"[A-Za-z]", username) is None:
            raise RegistrationError("Tên đăng nhập phải có ít nhất một chữ cái")

        if re.search(r"[0-9]", username) is None:
            raise RegistrationError("Tên đăng nhập phải có ít nhất một chữ số")

        return True

    def check_password(self, password: str) -> bool:
        if not 8 <= len(password) <= 64:
            raise RegistrationError("Mật khẩu phải có từ 8 đến 64 ký tự")

        if re.search(r"[A-Z]", password) is None:
            raise RegistrationError("Mật khẩu phải có ít nhất một chữ cái in hoa")

        if re.search(r"[0-9]", password) is None:
            raise RegistrationError("Mật khẩu phải có ít nhất một chữ số")

        if re.search(r"[^A-Za-z0-9]", password) is None:
            raise RegistrationError("Mật khẩu phải có ít nhất một ký tự đặc biệt")

        return True

    def check_email(self, email: str) -> bool:
        if not email:
            raise RegistrationError("Email không được để trống")

        if len(email) > 100:
            raise RegistrationError("Email không được vượt quá 100 ký tự")

        email_pattern = r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
        if re.fullmatch(email_pattern, email) is None:
            raise RegistrationError("Định dạng email không hợp lệ")

        return True

    def hash_password(self, password: str) -> str:
        return self.password_hash.hash(password)

    def register_user(self, username: str, password: str, email: str):
        # Username/password giữ nguyên, email chuẩn hóa để tìm kiếm nhất quán.
        email = email.strip().lower()

        self.check_username(username)
        self.check_password(password)
        self.check_email(email)

        if self.auth_repository.get_user_by_username(username) is not None:
            raise RegistrationError("Tên đăng nhập đã tồn tại", status_code=409)

        if self.auth_repository.get_user_by_email(email) is not None:
            raise RegistrationError("Email đã được sử dụng", status_code=409)

        user = self.auth_repository.add_user(
            username,
            self.hash_password(password),
            email,
        )

        if user is None:
            raise RegistrationError(
                "Tên đăng nhập hoặc email đã tồn tại", status_code=409
            )

        try:
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise RegistrationError(
                "Tên đăng nhập hoặc email đã tồn tại", status_code=409
            ) from exc

        return user
