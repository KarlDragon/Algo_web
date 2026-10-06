import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
from dotenv import load_dotenv
from jwt.exceptions import InvalidTokenError


class JWTService:
    def __init__(self):
        env_path = Path(__file__).resolve().parents[1] / ".env"
        load_dotenv(env_path)

        self.secret_key = os.getenv("JWT_SECRET_KEY")
        self.algorithm = os.getenv("JWT_ALGORITHM", "HS256")
        self.expire_minutes = int(
            os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
        )

        if not self.secret_key:
            raise ValueError(
                "JWT_SECRET_KEY khong ton tai trong file .env"
            )

    def create_access_token(self, user_id, username):
        now = datetime.now(timezone.utc)

        payload = {
            "sub": str(user_id),
            "username": username,
            "iat": now,
            "exp": now + timedelta(
                minutes=self.expire_minutes
            )
        }

        token = jwt.encode(
            payload,
            self.secret_key,
            algorithm=self.algorithm
        )

        return token

    def decode_access_token(self, token):
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm]
            )

            return payload

        except InvalidTokenError:
            return None