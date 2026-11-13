from datetime import timedelta
import secrets

from pwdlib import PasswordHash
from sqlalchemy.orm import Session

from Models.AuthToken import PasswordResetToken
from Models.Users import User
from Repositories.AuthRepository import AuthRepository
from Repositories.AuthTokenRepository import AuthTokenRepository
from Services.AuthError import AuthError
from Services.Register import RegisterService, RegistrationError
from Services.SessionService import token_hash, utc_now


class PasswordService:
    def __init__(self, session: Session):
        self.session = session
        self.user_repository = AuthRepository(session)
        self.tokens = AuthTokenRepository(session)
        self.password_hash = PasswordHash.recommended()

    def _validate_new(self, new_password: str, confirm_password: str) -> None:
        if new_password != confirm_password:
            raise AuthError("Xác nhận mật khẩu không khớp", 400)
        try:
            RegisterService(self.session).check_password(new_password)
        except RegistrationError as exc:
            raise AuthError(str(exc), 400) from exc

    def request_reset(self, email: str) -> tuple[User, str] | None:
        user = self.user_repository.get_user_by_email(email)
        if user is None:
            return None
        now = utc_now()
        # New request invalidates all previous reset links.
        self.tokens.invalidate_resets(user.id, now)
        raw_token = secrets.token_urlsafe(48)
        self.tokens.save_reset(PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash(raw_token),
            expires_at=now + timedelta(minutes=20),
        ))
        self.session.commit()
        return user, raw_token

    def reset(self, raw_token: str, new_password: str, confirm_password: str) -> User:
        self._validate_new(new_password, confirm_password)
        record = self.tokens.find_reset(token_hash(raw_token))
        now = utc_now()
        if record is None or record.used_at is not None or record.expires_at <= now:
            raise AuthError("Liên kết đặt lại mật khẩu không hợp lệ hoặc đã hết hạn", 400)
        user = self.user_repository.get_user_by_id(record.user_id)
        if user is None:
            raise AuthError("Liên kết đặt lại mật khẩu không hợp lệ hoặc đã hết hạn", 400)
        if self.password_hash.verify(new_password, user.hashPassword):
            raise AuthError("Mật khẩu mới phải khác mật khẩu cũ", 400)
        user.hashPassword = self.password_hash.hash(new_password)
        self.tokens.invalidate_resets(user.id, now)
        self.tokens.revoke_user(user.id, now)
        self.session.commit()
        return user

    def change(self, user: User, current_password: str,
               new_password: str, confirm_password: str) -> User:
        if not self.password_hash.verify(current_password, user.hashPassword):
            raise AuthError("Mật khẩu hiện tại không đúng", 400)
        self._validate_new(new_password, confirm_password)
        if self.password_hash.verify(new_password, user.hashPassword):
            raise AuthError("Mật khẩu mới phải khác mật khẩu cũ", 400)
        user.hashPassword = self.password_hash.hash(new_password)
        now = utc_now()
        self.tokens.invalidate_resets(user.id, now)
        self.tokens.revoke_user(user.id, now)
        self.session.commit()
        return user
