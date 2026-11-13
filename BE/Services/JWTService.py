import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
from dotenv import load_dotenv
from jwt.exceptions import InvalidTokenError


class JWTService:
    def __init__(self):
        load_dotenv(Path(__file__).resolve().parents[1] / ".env")
        self.secret_key = os.getenv("JWT_SECRET_KEY")
        self.algorithm = os.getenv("JWT_ALGORITHM", "HS256")
        self.expire_minutes = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
        if not self.secret_key:
            raise ValueError("Thiếu JWT_SECRET_KEY trong BE/.env")
        if self.algorithm != "HS256":
            raise ValueError("Chỉ hỗ trợ JWT_ALGORITHM=HS256")
        if self.expire_minutes < 1:
            raise ValueError("ACCESS_TOKEN_EXPIRE_MINUTES phải >= 1")

    @property
    def expires_in(self) -> int:
        return self.expire_minutes * 60

    def create_access_token(self, user_id: int, username: str, role: str = "USER") -> str:
        now = datetime.now(timezone.utc)
        payload = {
            "sub": str(user_id),
            "username": username,
            "role": role,
            "token_type": "access",
            "iat": now,
            "exp": now + timedelta(minutes=self.expire_minutes),
        }
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def decode_access_token(self, token: str) -> dict | None:
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm],
                options={"require": ["sub", "iat", "exp", "token_type"]},
            )
            if payload.get("token_type") != "access":
                return None
            if not str(payload.get("sub", "")).isdigit():
                return None
            return payload
        except (InvalidTokenError, ValueError, TypeError):
            return None
