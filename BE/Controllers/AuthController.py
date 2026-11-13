from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from database import get_db
from Models.Users import User
from Schemas.ChangePasswordRequest import ChangePasswordRequest
from Schemas.ForgotPasswordRequest import ForgotPasswordRequest
from Schemas.LoginRequest import LoginRequest
from Schemas.LogoutRequest import LogoutRequest
from Schemas.RefreshRequest import RefreshRequest
from Schemas.RegisterRequest import RegisterRequest
from Schemas.ResetPasswordRequest import ResetPasswordRequest
from Services.AuthDependencies import get_current_user
from Services.AuthError import AuthError
from Services.Login import LoginService
from Services.MailService import MailService
from Services.PasswordService import PasswordService
from Services.RateLimiter import auth_rate_limiter
from Services.Register import RegisterService, RegistrationError
from Services.SessionService import SessionService


class AuthController:
    def __init__(self):
        self.router = APIRouter(prefix="/auth", tags=["Authentication"])
        self.router.add_api_route("/register", self.register, methods=["POST"], status_code=201)
        self.router.add_api_route("/login", self.login, methods=["POST"])
        self.router.add_api_route("/refresh", self.refresh, methods=["POST"])
        self.router.add_api_route("/logout", self.logout, methods=["POST"])
        self.router.add_api_route("/forgot-password", self.forgot_password, methods=["POST"])
        self.router.add_api_route("/reset-password", self.reset_password, methods=["POST"])
        self.router.add_api_route("/change-password", self.change_password, methods=["POST"])

    @staticmethod
    def _raise_http(exc: AuthError | RegistrationError) -> None:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    @staticmethod
    def _check_limit(key: str, limit: int, window_seconds: int) -> None:
        try:
            auth_rate_limiter.check(key, limit, window_seconds)
        except AuthError as exc:
            raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    @staticmethod
    def _client_key(request: Request, action: str) -> str:
        # Do not trust X-Forwarded-For without a configured trusted reverse proxy.
        return f"{action}:{request.client.host if request.client else 'unknown'}"

    def register(self, data: RegisterRequest, request: Request,
                 background_tasks: BackgroundTasks, session: Session = Depends(get_db)):
        self._check_limit(self._client_key(request, "register"), 10, 600)
        try:
            user = RegisterService(session).register_user(
                data.username, data.password, data.email
            )
        except RegistrationError as exc:
            self._raise_http(exc)
        background_tasks.add_task(MailService().welcome, user.email, user.username)
        return {"id": user.id, "username": user.username, "email": user.email, "role": user.role}

    def login(self, data: LoginRequest, request: Request,
              session: Session = Depends(get_db)):
        key = f"{self._client_key(request, 'login')}:{data.login.strip().lower()}"
        self._check_limit(self._client_key(request, "login-ip"), 100, 900)
        self._check_limit(key, 5, 900)
        user = LoginService(session).login_user(data.login, data.password)
        if user is None:
            raise HTTPException(401, detail="Tên đăng nhập/email hoặc mật khẩu không đúng")
        auth_rate_limiter.clear(key)
        tokens = SessionService(session).issue(user, data.remember_me)
        return {
            "message": "Đăng nhập thành công", **tokens,
            "user": {"id": user.id, "username": user.username, "email": user.email, "role": user.role},
        }

    def refresh(self, data: RefreshRequest, request: Request,
                session: Session = Depends(get_db)):
        self._check_limit(self._client_key(request, "refresh"), 50, 60)
        try:
            return SessionService(session).refresh(data.refresh_token)
        except AuthError as exc:
            self._raise_http(exc)

    def logout(self, data: LogoutRequest, request: Request,
               session: Session = Depends(get_db),
               current_user: User = Depends(get_current_user)):
        self._check_limit(self._client_key(request, "logout"), 30, 60)
        try:
            SessionService(session).logout(current_user, data.refresh_token)
        except AuthError as exc:
            self._raise_http(exc)
        return {"message": "Đăng xuất thành công"}

    def forgot_password(self, data: ForgotPasswordRequest, request: Request,
                        background_tasks: BackgroundTasks,
                        session: Session = Depends(get_db)):
        self._check_limit(self._client_key(request, "forgot"), 5, 600)
        result = PasswordService(session).request_reset(data.email)
        if result is not None:
            user, token = result
            background_tasks.add_task(MailService().reset_link, user.email, token)
        return {"message": "Nếu email tồn tại, liên kết đặt lại mật khẩu đã được gửi"}

    def reset_password(self, data: ResetPasswordRequest, request: Request,
                       background_tasks: BackgroundTasks,
                       session: Session = Depends(get_db)):
        self._check_limit(self._client_key(request, "reset"), 10, 600)
        try:
            user = PasswordService(session).reset(
                data.token, data.new_password, data.confirm_password
            )
        except AuthError as exc:
            self._raise_http(exc)
        background_tasks.add_task(MailService().password_changed, user.email)
        return {"message": "Đổi mật khẩu thành công"}

    def change_password(self, data: ChangePasswordRequest, request: Request,
                        background_tasks: BackgroundTasks,
                        session: Session = Depends(get_db),
                        current_user: User = Depends(get_current_user)):
        limit_key = f"{self._client_key(request, 'change')}:{current_user.id}"
        self._check_limit(limit_key, 5, 900)
        try:
            user = PasswordService(session).change(
                current_user, data.current_password, data.new_password,
                data.confirm_password
            )
        except AuthError as exc:
            self._raise_http(exc)
        background_tasks.add_task(MailService().password_changed, user.email)
        return {"message": "Đổi mật khẩu thành công"}
