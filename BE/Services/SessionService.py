"""Issue opaque refresh tokens, rotate on each use, revoke sessions on logout."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import secrets
from uuid import uuid4

from sqlalchemy.orm import Session

from Models.AuthToken import RefreshToken
from Models.Users import User
from Repositories.AuthRepository import AuthRepository
from Repositories.AuthTokenRepository import AuthTokenRepository
from Services.AuthError import AuthError
from Services.JWTService import JWTService


def utc_now() -> datetime:
    # DB fields are UTC-naive for SQLite portability.
    return datetime.now(timezone.utc).replace(tzinfo=None)


def token_hash(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


class SessionService:
    def __init__(self, session: Session):
        self.session = session
        self.repository = AuthTokenRepository(session)
        self.jwt_service = JWTService()

    def _create_refresh(self, user: User, family: str, ttl_days: int) -> str:
        token = secrets.token_urlsafe(48)
        self.repository.save_refresh(RefreshToken(
            user_id=user.id,
            token_hash=token_hash(token),
            family_id=family,
            expires_at=utc_now() + timedelta(days=ttl_days),
        ))
        return token

    def issue(self, user: User, remember_me: bool = False) -> dict:
        family = str(uuid4())
        refresh_token = self._create_refresh(user, family, 30 if remember_me else 7)
        self.session.commit()
        return {
            "access_token": self.jwt_service.create_access_token(user.id, user.username, user.role),
            "refresh_token": refresh_token,
            "expires_in": self.jwt_service.expires_in,
            "token_type": "bearer",
        }

    def refresh(self, raw_token: str) -> dict:
        record = self.repository.find_refresh(token_hash(raw_token))
        now = utc_now()
        if record is None:
            raise AuthError("Refresh token không hợp lệ hoặc đã hết hạn", 401)

        if record.revoked_at is not None:
            # A rotated token replay revokes its entire session family.
            if record.replaced_at is not None:
                self.repository.revoke_family(record.family_id, now)
                self.session.commit()
            raise AuthError("Refresh token không hợp lệ hoặc đã hết hạn", 401)

        if record.expires_at <= now:
            record.revoked_at = now
            self.session.commit()
            raise AuthError("Refresh token không hợp lệ hoặc đã hết hạn", 401)

        user = AuthRepository(self.session).get_user_by_id(record.user_id)
        if user is None:
            raise AuthError("Refresh token không hợp lệ hoặc đã hết hạn", 401)

        record.revoked_at = now
        record.replaced_at = now
        remaining = record.expires_at - now
        ttl_seconds = max(1, int(remaining.total_seconds()))
        new_token = secrets.token_urlsafe(48)
        self.repository.save_refresh(RefreshToken(
            user_id=user.id,
            token_hash=token_hash(new_token),
            family_id=record.family_id,
            expires_at=now + timedelta(seconds=ttl_seconds),
        ))
        self.session.commit()
        return {
            "access_token": self.jwt_service.create_access_token(user.id, user.username, user.role),
            "refresh_token": new_token,
            "expires_in": self.jwt_service.expires_in,
            "token_type": "bearer",
        }

    def logout(self, user: User, raw_token: str) -> None:
        record = self.repository.find_refresh(token_hash(raw_token))
        if record is None or record.user_id != user.id:
            raise AuthError("Refresh token không hợp lệ", 401)
        # Revoke all tokens of the session family (including rotated token).
        self.repository.revoke_family(record.family_id, utc_now())
        self.session.commit()

    def revoke_all(self, user_id: int) -> None:
        self.repository.revoke_user(user_id, utc_now())
