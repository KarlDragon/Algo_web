from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from Schemas.RegisterRequest import RegisterRequest
from Services.Register import RegisterService
from database import get_db


class AuthController:

    def __init__(self):
        self.router = APIRouter(
            tags=["Authentication"]
        )

        self.router.add_api_route(
            "/register",
            self.register,
            methods=["POST"],
            status_code=201
        )

    def register(
        self,
        data: RegisterRequest,
        session: Session = Depends(get_db)
    ):
        register_service = RegisterService(session)
        user = register_service.register_user(
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