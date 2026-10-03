from fastapi import APIRouter, HTTPException

from Schemas.RegisterRequest import RegisterRequest
from Services.Register import RegisterService


class AuthController:

    def __init__(self):
        self.router = APIRouter(
            tags=["Authentication"]
        )

        self.register_service = RegisterService()

        self.router.add_api_route(
            "/register",
            self.register,
            methods=["POST"],
            status_code=201
        )

    def register(self, data: RegisterRequest):
        user = self.register_service.register_user(
            data.username,
            data.password,
            data.email
        )

        if user is None:
            raise HTTPException(
                status_code=400,
                detail="Register failed"
            )

        return {
            "id": user.id,
            "username": user.username,
            "email": user.email
        }