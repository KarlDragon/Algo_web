from sqlalchemy import select, update
from sqlalchemy.orm import Session

from Models.AuthToken import PasswordResetToken, RefreshToken


class AuthTokenRepository:
    def __init__(self, session: Session):
        self.session = session

    def find_refresh(self, token_hash: str) -> RefreshToken | None:
        return self.session.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))

    def save_refresh(self, token: RefreshToken) -> None:
        self.session.add(token)
        self.session.flush()

    def revoke_family(self, family_id: str, now) -> None:
        self.session.execute(
            update(RefreshToken).where(
                RefreshToken.family_id == family_id,
                RefreshToken.revoked_at.is_(None),
            ).values(revoked_at=now)
        )

    def revoke_user(self, user_id: int, now) -> None:
        self.session.execute(
            update(RefreshToken).where(
                RefreshToken.user_id == user_id,
                RefreshToken.revoked_at.is_(None),
            ).values(revoked_at=now)
        )

    def find_reset(self, token_hash: str) -> PasswordResetToken | None:
        return self.session.scalar(
            select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
        )

    def save_reset(self, token: PasswordResetToken) -> None:
        self.session.add(token)

    def invalidate_resets(self, user_id: int, now) -> None:
        self.session.execute(
            update(PasswordResetToken).where(
                PasswordResetToken.user_id == user_id,
                PasswordResetToken.used_at.is_(None),
            ).values(used_at=now)
        )
