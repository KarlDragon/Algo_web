from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from Schemas.LoginRequest import LoginRequest
from Schemas.RegisterRequest import RegisterRequest
from Services.JWTService import JWTService
from Services.Login import LoginService
from Services.Register import RegisterService


class AuthController:
    def __init__(self):
        self.router = APIRouter(
            tags=["Authentication"]
        )

        self.jwt_service = JWTService()

        self.router.add_api_route(
            "/register",
            self.register,
            methods=["POST"],
            status_code=201
        )

        self.router.add_api_route(
            "/login",
            self.login,
            methods=["POST"],
            status_code=200
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

    def login(
        self,
        data: LoginRequest,
        session: Session = Depends(get_db)
    ):
        login_service = LoginService(session)

        user = login_service.login_user(
            data.login,
            data.password
        )

        if user is None:
            raise HTTPException(
                status_code=401,
                detail="Username/email hoac password khong dung"
            )

        access_token = self.jwt_service.create_access_token(
            user.id,
            user.username
        )

        return {
            "message": "Dang nhap thanh cong",
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email
            }
        }