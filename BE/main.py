from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from Controllers.AuthController import AuthController
from Models.Users import User
from Models.AuthToken import RefreshToken, PasswordResetToken  # Register models before create_all
from database import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Only creates missing tables. Run 'alembic upgrade head' for new columns.
    User.metadata.create_all(bind=engine)
    yield


app = FastAPI(lifespan=lifespan)


@app.exception_handler(RequestValidationError)
async def invalid_request(request: Request, exc: RequestValidationError):
    first = exc.errors()[0] if exc.errors() else {}
    if first.get("type") == "json_invalid":
        message = "JSON không hợp lệ"
    else:
        field = str(first.get("loc", ["dữ liệu"])[-1])
        friendly = {
            "username": "tên đăng nhập", "password": "mật khẩu",
            "email": "email", "login": "tài khoản đăng nhập",
            "refresh_token": "refresh token", "new_password": "mật khẩu mới",
            "confirm_password": "xác nhận mật khẩu",
            "current_password": "mật khẩu hiện tại",
        }.get(field, field)
        message = f"Thiếu hoặc sai định dạng trường {friendly}"
    return JSONResponse(status_code=400, content={"detail": message})


auth_controller = AuthController()
app.include_router(auth_controller.router)
