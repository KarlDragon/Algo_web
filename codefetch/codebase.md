<source_code>
BE/database.py
```
import os
from collections.abc import Iterator
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

database_url = os.getenv("DATABASE_URL")
if not database_url:
    raise ValueError("DATABASE_URL khong ton tai trong file .env")

echo_sql = os.getenv("SQLALCHEMY_ECHO", "").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}

engine = create_engine(database_url, echo=echo_sql)
SessionLocal = sessionmaker(bind=engine)


def get_db() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session
```

BE/main.py
```
from contextlib import asynccontextmanager

from fastapi import FastAPI

from Controllers.AuthController import AuthController
from Models.Users import User
from database import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    User.metadata.create_all(bind=engine)
    yield


app = FastAPI(lifespan=lifespan)
auth_controller = AuthController()

app.include_router(
    auth_controller.router
)
```

FE/eslint.config.js
```
import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'
import { globalIgnores } from 'eslint/config'

export default tseslint.config([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      reactHooks.configs['recommended-latest'],
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
    },
  },
])
```

FE/index.html
```
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <meta name="description" content="Log in or create an Algo Web account." />
    <title>Algo Web | Account</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

FE/package.json
```
{
  "name": "algo-web-fe",
  "private": true,
  "version": "0.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "lint": "eslint .",
    "preview": "vite preview"
  },
  "dependencies": {
    "bootstrap": "^5.3.8",
    "react": "^19.1.1",
    "react-bootstrap": "^2.10.10",
    "react-dom": "^19.1.1"
  },
  "devDependencies": {
    "@eslint/js": "^9.33.0",
    "@types/react": "^19.1.10",
    "@types/react-dom": "^19.1.7",
    "@vitejs/plugin-react": "^5.0.0",
    "eslint": "^9.33.0",
    "eslint-plugin-react-hooks": "^5.2.0",
    "eslint-plugin-react-refresh": "^0.4.20",
    "globals": "^16.3.0",
    "typescript": "~5.8.3",
    "typescript-eslint": "^8.39.1",
    "vite": "^7.1.2"
  }
}
```

FE/tsconfig.app.json
```
{
  "compilerOptions": {
    "tsBuildInfoFile": "./node_modules/.tmp/tsconfig.app.tsbuildinfo",
    "target": "ES2022",
    "useDefineForClassFields": true,
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,

    /* Bundler mode */
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "verbatimModuleSyntax": true,
    "moduleDetection": "force",
    "noEmit": true,
    "jsx": "react-jsx",

    /* Linting */
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "erasableSyntaxOnly": true,
    "noFallthroughCasesInSwitch": true,
    "noUncheckedSideEffectImports": true
  },
  "include": ["src"]
}
```

FE/tsconfig.json
```
{
  "files": [],
  "references": [
    { "path": "./tsconfig.app.json" },
    { "path": "./tsconfig.node.json" }
  ]
}
```

FE/tsconfig.node.json
```
{
  "compilerOptions": {
    "tsBuildInfoFile": "./node_modules/.tmp/tsconfig.node.tsbuildinfo",
    "target": "ES2023",
    "lib": ["ES2023"],
    "module": "ESNext",
    "skipLibCheck": true,

    /* Bundler mode */
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "verbatimModuleSyntax": true,
    "moduleDetection": "force",
    "noEmit": true,

    /* Linting */
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "erasableSyntaxOnly": true,
    "noFallthroughCasesInSwitch": true,
    "noUncheckedSideEffectImports": true
  },
  "include": ["vite.config.ts"]
}
```

FE/vite.config.ts
```
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
```

BE/Controllers/AuthController.py
```
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
```

BE/Models/Base.py
```
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
```

BE/Models/Users.py
```
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from Models.Base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True
    )

    username: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        unique=True
    )

    hashPassword: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )

    email: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True
    )
```

BE/Repositories/AuthRepository.py
```
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from Models.Users import User


class AuthRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_user_by_username(self, username):
        statement = select(User).where(
            User.username == username
        )
        return self.session.scalar(statement)

    def get_user_by_email(self, email):
        statement = select(User).where(
            User.email == email
        )
        return self.session.scalar(statement)

    def get_user_by_username_or_email(self, login):
        statement = select(User).where(
            or_(
                User.username == login,
                User.email == login
            )
        )
        return self.session.scalar(statement)

    def add_user(self, username, hashPassword, email):
        user = User(
            username=username,
            hashPassword=hashPassword,
            email=email
        )

        self.session.add(user)

        try:
            self.session.flush()
            self.session.refresh(user)
            return user

        except IntegrityError:
            self.session.rollback()
            return None
```

BE/Schemas/LoginRequest.py
```
from pydantic import BaseModel


class LoginRequest(BaseModel):
    login: str
    password: str
```

BE/Schemas/RegisterRequest.py
```
from pydantic import BaseModel


class RegisterRequest(BaseModel):
    username: str
    password: str
    email: str
```

BE/Services/JWTService.py
```
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
```

BE/Services/Login.py
```
from pwdlib import PasswordHash
from sqlalchemy.orm import Session

from Repositories.AuthRepository import AuthRepository


class LoginService:
    def __init__(self, session: Session):
        self.auth_repository = AuthRepository(session)
        self.password_hash = PasswordHash.recommended()

    def verify_password(self, password, hashed_password):
        return self.password_hash.verify(
            password,
            hashed_password
        )

    def login_user(self, login, password):
        if login == "" or password == "":
            return None

        user = self.auth_repository.get_user_by_username_or_email(
            login
        )

        if user is None:
            return None

        if not self.verify_password(
            password,
            user.hashPassword
        ):
            return None

        return user
```

BE/Services/Register.py
```
import re

from pwdlib import PasswordHash
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from Repositories.AuthRepository import AuthRepository


class RegisterService:

    def __init__(self, session: Session):
        self.session = session
        self.auth_repository = AuthRepository(session)
        self.password_hash = PasswordHash.recommended()

    def check_username(self, username):
        if username == "":
            print("Username khong duoc rong!")
            return False

        if len(username) > 50:
            print("Username khong duoc qua 50 ky tu!")
            return False

        if not re.search(r"[A-Za-z]", username):
            print("Username phai co it nhat 1 chu cai!")
            return False

        if not re.search(r"[0-9]", username):
            print("Username phai co it nhat 1 chu so!")
            return False

        return True

    def check_password(self, password):
        if password == "":
            print("Password khong duoc rong!")
            return False

        if len(password) < 8:
            print("Password phai co it nhat 8 ky tu!")
            return False

        if len(password) > 64:
            print("Password khong duoc qua 64 ky tu!")
            return False

        if not re.search(r"[A-Z]", password):
            print("Password phai co it nhat 1 chu cai in hoa!")
            return False

        if not re.search(r"[0-9]", password):
            print("Password phai co it nhat 1 chu so!")
            return False

        if not re.search(r"[^A-Za-z0-9]", password):
            print("Password phai co it nhat 1 ky tu dac biet!")
            return False

        return True

    def check_email(self, email):
        if email == "":
            print("Email khong duoc rong!")
            return False

        if len(email) > 100:
            print("Email khong duoc qua 100 ky tu!")
            return False

        email_pattern = (
            r"^[A-Za-z0-9._%+-]+@"
            r"[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"
        )

        if not re.match(email_pattern, email):
            print("Email khong hop le!")
            return False

        return True

    def hash_password(self, password):
        return self.password_hash.hash(password)

    def register_user(self, username, password, email):
        if not self.check_username(username):
            return None

        if not self.check_password(password):
            return None

        if not self.check_email(email):
            return None

        existing_username = (
            self.auth_repository.get_user_by_username(username)
        )

        if existing_username is not None:
            print("Username da ton tai!")
            return None

        existing_email = (
            self.auth_repository.get_user_by_email(email)
        )

        if existing_email is not None:
            print("Email da ton tai!")
            return None

        hashed_password = self.hash_password(password)

        user = self.auth_repository.add_user(
            username,
            hashed_password,
            email
        )

        if user is None:
            return None

        try:
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            return None

        return user
```

FE/src/App.css
```
.night-sky-canvas {
  position: fixed;
  inset: 0;
  z-index: -1;
  display: block;
  width: 100%;
  height: 100%;
  background: radial-gradient(
    ellipse at 50% 110%,
    #0d1d38 0%,
    #050a16 60%,
    #03050c 100%
  );
  pointer-events: none;
  touch-action: none;
}

.auth-page {
  display: grid;
  min-height: 100vh;
  place-items: center;
  padding: 2rem 1rem;
}

.auth-card {
  width: min(100%, 26rem);
  padding: 2rem;
  border: 1px solid #dedede;
  border-radius: 0.75rem;
  background: #fff;
}

.auth-header {
  margin-bottom: 1.5rem;
}

.auth-header h1 {
  margin: 0;
  font-size: 1.75rem;
  font-weight: 650;
  letter-spacing: -0.035em;
}

.auth-header p {
  margin: 0.5rem 0 0;
  color: #666;
  line-height: 1.5;
}

.auth-tabs {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.25rem;
  margin-bottom: 1.5rem;
  padding: 0.25rem;
  border: 1px solid #e4e4e4;
  border-radius: 0.5rem;
}

.auth-tab {
  min-height: 2.5rem;
  border: 0;
  border-radius: 0.3rem;
  background: transparent;
  color: #555;
  cursor: pointer;
  font: inherit;
}

.auth-tab.is-active {
  background: #ededed;
  color: #111;
}

.auth-form {
  display: grid;
  gap: 1.15rem;
}

.form-field {
  display: grid;
  gap: 0.45rem;
  font-size: 0.925rem;
  font-weight: 550;
}

.form-field input {
  box-sizing: border-box;
  width: 100%;
  min-height: 2.8rem;
  padding: 0.65rem 0.75rem;
  border: 1px solid #cfcfcf;
  border-radius: 0.4rem;
  background: #fff;
  color: #171717;
  font: inherit;
  font-weight: 400;
}

.form-field input:focus-visible,
.auth-tab:focus-visible,
.submit-button:focus-visible,
.text-button:focus-visible {
  outline: 2px solid #222;
  outline-offset: 2px;
}

.field-hint {
  color: #666;
  font-size: 0.8rem;
  font-weight: 400;
  line-height: 1.45;
}

.submit-button {
  min-height: 2.8rem;
  margin-top: 0.25rem;
  border: 1px solid #111;
  border-radius: 0.4rem;
  background: #111;
  color: #fff;
  cursor: pointer;
  font: inherit;
  font-weight: 600;
}

.submit-button:disabled {
  cursor: wait;
  opacity: 0.65;
}

.form-status {
  margin: 1rem 0 0;
  padding: 0.8rem 0.9rem;
  border: 1px solid #dedede;
  border-radius: 0.4rem;
  font-size: 0.9rem;
  line-height: 1.5;
  overflow-wrap: anywhere;
}

.form-status p {
  margin: 0;
}

.form-status p + p {
  margin-top: 0.35rem;
}

.is-error {
  border-color: #b7b7b7;
  color: #222;
}

.is-success {
  background: #f7f7f7;
  color: #222;
}

.text-button {
  margin-top: 0.65rem;
  padding: 0;
  border: 0;
  background: transparent;
  color: #111;
  cursor: pointer;
  font: inherit;
  font-weight: 600;
  text-decoration: underline;
  text-underline-offset: 0.15em;
}

@media (max-width: 24rem) {
  .auth-card {
    padding: 1.35rem;
  }
}
```

FE/src/App.tsx
```
import { useState } from 'react'
import './App.css'
import AuthForm from './components/AuthForm'
import NightSkyCanvas from './components/NightSkyCanvas'
import { useAuth } from './hooks/useAuth'
import type { AuthMode } from './models/auth'

function App() {
  const [mode, setMode] = useState<AuthMode>('login')
  const { status, isSubmitting, submit, clearStatus } = useAuth()

  function changeMode(nextMode: AuthMode) {
    setMode(nextMode)
    clearStatus()
  }

  return (
    <>
      <NightSkyCanvas />
      <AuthForm
        isSubmitting={isSubmitting}
        mode={mode}
        onModeChange={changeMode}
        onSubmit={submit}
        status={status}
      />
    </>
  )
}

export default App
```

FE/src/index.css
```
:root {
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont,
    "Segoe UI", sans-serif;
  color: #171717;
  font-synthesis: none;
  text-rendering: optimizeLegibility;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;

  font-optical-sizing: auto;
  font-weight: 400;
}

* {
  box-sizing: border-box;
}

body {
  min-width: 320px;
  min-height: 100vh;
  margin: 0;
}

button,
input {
  font-family: inherit;
}

button:focus-visible {
  outline: 2px solid #222;
  outline-offset: 2px;
}
```

FE/src/main.tsx
```
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
```

FE/src/vite-env.d.ts
```
/// <reference types="vite/client" />
```

FE/src/components/AuthForm.tsx
```
import type { FormEvent } from 'react'
import type {
  AuthMode,
  AuthStatus,
  AuthSubmission,
} from '../models/auth'
import LoginFields from './LoginFields'
import RegisterFields from './RegisterFields'

type AuthFormProps = {
  isSubmitting: boolean
  mode: AuthMode
  onModeChange: (mode: AuthMode) => void
  onSubmit: (submission: AuthSubmission) => Promise<void>
  status: AuthStatus | null
}

function AuthForm({
  isSubmitting,
  mode,
  onModeChange,
  onSubmit,
  status,
}: AuthFormProps) {
  const isRegistering = mode === 'register'

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    const formData = new FormData(event.currentTarget)

    if (mode === 'login') {
      void onSubmit({
        mode: 'login',
        data: {
          login: String(formData.get('login') ?? ''),
          password: String(formData.get('password') ?? ''),
        },
      })
      return
    }

    void onSubmit({
      mode: 'register',
      data: {
        username: String(formData.get('username') ?? ''),
        password: String(formData.get('password') ?? ''),
        email: String(formData.get('email') ?? ''),
      },
    })
  }

  return (
    <main className="auth-page">
      <section className="auth-card" aria-labelledby="auth-title">
        <header className="auth-header">
          <h1 id="auth-title">
            {isRegistering ? 'Tạo tài khoản mới' : 'Chào mừng!'}
          </h1>
          <p>
            {isRegistering
              ? 'Vui lòng nhập thông tin.'
              : 'Tên đăng nhập hoặc email.'}
          </p>
        </header>

        <div className="auth-tabs" role="group" aria-label="Account action">
          <button
            aria-pressed={!isRegistering}
            className={!isRegistering ? 'auth-tab is-active' : 'auth-tab'}
            disabled={isSubmitting}
            onClick={() => onModeChange('login')}
            type="button"
          >
            Đăng nhập
          </button>
          <button
            aria-pressed={isRegistering}
            className={isRegistering ? 'auth-tab is-active' : 'auth-tab'}
            disabled={isSubmitting}
            onClick={() => onModeChange('register')}
            type="button"
          >
            Đăng ký
          </button>
        </div>

        <form className="auth-form" onSubmit={handleSubmit}>
          {isRegistering ? <RegisterFields /> : <LoginFields />}

          {status?.kind === 'error' && (
            <p className="form-status is-error" role="alert">
              {status.message}
            </p>
          )}

          <button className="submit-button" disabled={isSubmitting} type="submit">
            {isSubmitting
              ? 'Chờ trong giây lát…'
              : isRegistering
                ? 'Đăng ký'
                : 'Đăng nhập'}
          </button>
        </form>

        {status?.kind === 'login-success' && (
          <div className="form-status is-success" role="status">
            <p>{status.message}</p>
            <p>
              Signed in as <strong>{status.user.username}</strong> (
              {status.user.email})
            </p>
          </div>
        )}

        {status?.kind === 'register-success' && (
          <div className="form-status is-success" role="status">
            <p>
              Account created for <strong>{status.user.username}</strong> (
              {status.user.email}).
            </p>
            <button
              className="text-button"
              onClick={() => onModeChange('login')}
              type="button"
            >
              Continue to log in
            </button>
          </div>
        )}
      </section>
    </main>
  )
}

export default AuthForm
```

FE/src/components/LoginFields.tsx
```
function LoginFields() {
  return (
    <>
      <div className="form-field">
        <label htmlFor="login">Tên đăng nhập hoặc email</label>
        <input
          autoComplete="username"
          id="login"
          name="login"
          required
        />
      </div>

      <div className="form-field">
        <label htmlFor="login-password">Mật khẩu</label>
        <input
          autoComplete="current-password"
          id="login-password"
          name="password"
          required
          type="password"
        />
      </div>
    </>
  )
}

export default LoginFields
```

FE/src/components/NightSkyCanvas.tsx
```
import { useEffect, useRef } from 'react'

type Particle = {
  sx: number
  sy: number
  sz: number
  th: number
  x: number
  y: number
  vy: number
  sp: number
  len: number
  l: number
  dx: number
  dy: number
  a: number
  b: number
  cap: boolean
}

type Star = {
  x: number
  y: number
  p: number
  s: number
}

function NightSkyCanvas() {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    if (!canvasRef.current) {
      return
    }

    const cv = canvasRef.current
    const context = cv.getContext('2d')
    if (!context) {
      return
    }

    const ctx = context
    let W = 0
    let H = 0
    let dpr: number

    function resize() {
      dpr = Math.min(window.devicePixelRatio || 1, 2)
      W = window.innerWidth
      H = window.innerHeight
      cv.width = W * dpr
      cv.height = H * dpr
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    }

    window.addEventListener('resize', resize)
    resize()

    // ---- Cấu hình (chỉnh ở đây) ----
    const N = W < 700 ? 33 : 60
    const FALL = [70, 260]
    const CHARGE_UP = 0.4
    const CHARGE_DOWN = 0.35
    const ROT = 0.45
    const TILT = 0.38
    const BUCKETS = 5
    const LEN = 4
    const RANGE_K = 0.28

    const ga = Math.PI * (3 - Math.sqrt(5))
    const ps: Particle[] = []

    for (let i = 0; i < N; i++) {
      const y = 1 - (2 * (i + 0.5)) / N
      const r = Math.sqrt(1 - y * y)
      const t = ga * i
      ps.push({
        sx: Math.cos(t) * r,
        sy: y,
        sz: Math.sin(t) * r,
        th: Math.random() * 0.85,
        x: Math.random() * W,
        y: Math.random() * H,
        vy: 0,
        sp: FALL[0] + Math.random() * (FALL[1] - FALL[0]),
        len: (8 + Math.random() * 16) * LEN,
        l: 12 * LEN,
        dx: 0,
        dy: -1,
        a: 0.3 + Math.random() * 0.6,
        b: 0,
        cap: false,
      })
    }

    const stars: Star[] = []
    for (let i = 0; i < 90; i++) {
      stars.push({
        x: Math.random(),
        y: Math.random() * 0.9,
        p: Math.random() * 6.28,
        s: Math.random() * 0.8 + 0.4,
      })
    }

    let mx = W / 2
    let my = H / 2
    let cx = mx
    let cy = my
    let last = -1e9
    let charge = 0
    let prev = performance.now()
    let time = 0
    let animationFrame = 0

    function move(e: PointerEvent) {
      mx = e.clientX
      my = e.clientY
      last = performance.now()
    }

    window.addEventListener('pointermove', move)
    window.addEventListener('pointerdown', move)

    function frame(now: number) {
      const dt = Math.min((now - prev) / 1000, 0.05)
      prev = now
      time += dt
      ctx.clearRect(0, 0, W, H)

      ctx.fillStyle = '#cfe4ff'
      for (let i = 0; i < stars.length; i++) {
        const s = stars[i]
        ctx.globalAlpha =
          0.25 +
          0.35 *
            Math.sin(time * s.s + s.p) *
            Math.sin(time * s.s + s.p)
        ctx.fillRect(s.x * W, s.y * H, 1.2, 1.2)
      }

      const active = now - last < 1500
      charge += (active ? CHARGE_UP : -CHARGE_DOWN) * dt
      charge = Math.max(0, Math.min(1, charge))
      const k = 1 - Math.exp(-6 * dt)
      cx += (mx - cx) * k
      cy += (my - cy) * k

      const R = Math.max(64, Math.min(W, H) * 0.141)
      const RANGE = Math.max(140, Math.min(W, H) * RANGE_K)
      const ang = time * ROT
      const ca = Math.cos(ang)
      const sa = Math.sin(ang)
      const ct = Math.cos(TILT)
      const st = Math.sin(TILT)
      const kd = 1 - Math.exp(-8 * dt)

      for (let i = 0; i < N; i++) {
        const p = ps[i]
        let tdx: number
        let tdy: number
        let tl: number
        let alpha: number

        if (charge <= p.th) p.cap = false
        else if (!p.cap && Math.hypot(p.x - cx, p.y - cy) < RANGE) {
          p.cap = true
        }

        if (p.cap) {
          const x1 = p.sx * ca + p.sz * sa
          const z1 = -p.sx * sa + p.sz * ca
          const y2 = p.sy * ct - z1 * st
          const z2 = p.sy * st + z1 * ct
          const d = (z2 + 1) / 2
          const sc = 0.8 + 0.4 * d
          const tx = cx + x1 * R * sc
          const ty = cy + y2 * R * sc
          const e = 1 - Math.exp(-(2.5 + p.sp / 60) * dt)
          p.x += (tx - p.x) * e
          p.y += (ty - p.y) * e
          p.vy = 0
          const m = Math.hypot(x1, y2) + 1e-4
          tdx = x1 / m
          tdy = y2 / m
          tl = p.len * 0.45 * (0.35 + 0.65 * m) * sc
          alpha = Math.min(1, p.a * 0.35 + 0.25 + 0.55 * d)
        } else {
          p.vy += (p.sp - p.vy) * (1 - Math.exp(-2 * dt))
          p.y += p.vy * dt
          tdx = 0
          tdy = -1
          tl = p.len
          alpha = p.a
          if (p.y - p.len > H) {
            p.y = -p.len - Math.random() * H * 0.3
            p.x = Math.random() * W
          }
        }

        p.dx += (tdx - p.dx) * kd
        p.dy += (tdy - p.dy) * kd
        p.l += (tl - p.l) * kd
        p.b = Math.min(BUCKETS - 1, (alpha * BUCKETS) | 0)
      }

      ctx.lineCap = 'round'
      ctx.lineWidth = 1.4
      for (let b = 0; b < BUCKETS; b++) {
        ctx.globalAlpha = (b + 1) / BUCKETS
        ctx.strokeStyle = `hsl(200,90%,${66 + b * 4}%)`
        ctx.beginPath()
        for (let i = 0; i < N; i++) {
          const q = ps[i]
          if (q.b !== b) continue
          ctx.moveTo(q.x, q.y)
          ctx.lineTo(q.x + q.dx * q.l, q.y + q.dy * q.l)
        }
        ctx.stroke()
      }

      ctx.globalAlpha = 1
      animationFrame = window.requestAnimationFrame(frame)
    }

    animationFrame = window.requestAnimationFrame(frame)

    return () => {
      window.cancelAnimationFrame(animationFrame)
      window.removeEventListener('resize', resize)
      window.removeEventListener('pointermove', move)
      window.removeEventListener('pointerdown', move)
    }
  }, [])

  return <canvas aria-hidden="true" className="night-sky-canvas" ref={canvasRef} />
}

export default NightSkyCanvas
```

FE/src/components/RegisterFields.tsx
```
function RegisterFields() {
  return (
    <>
      <div className="form-field">
        <label htmlFor="username">Tên đăng nhập</label>
        <input
          aria-describedby="username-hint"
          autoComplete="username"
          id="username"
          maxLength={50}
          name="username"
          pattern="(?=.*[A-Za-z])(?=.*[0-9]).*"
          required
          title="Use at least one letter and one number."
        />
        <span className="field-hint" id="username-hint">
          Phải có 1 chữ và 1 số.
        </span>
      </div>

      <div className="form-field">
        <label htmlFor="email">Email</label>
        <input
          autoComplete="email"
          id="email"
          maxLength={100}
          name="email"
          pattern="[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}"
          required
          type="email"
        />
      </div>

      <div className="form-field">
        <label htmlFor="register-password">Mật khẩu</label>
        <input
          aria-describedby="password-hint"
          autoComplete="new-password"
          id="register-password"
          maxLength={64}
          minLength={8}
          name="password"
          pattern="(?=.*[A-Z])(?=.*[0-9])(?=.*[^A-Za-z0-9]).{8,64}"
          required
          title="Mật khẩu ít nhất 8 ký tự, có chữ cái in hoa, số và ký tự đặc biệt"
          type="password"
        />
        <span className="field-hint" id="password-hint">
          Mật khẩu ít nhất 8 ký tự, có chữ cái in hoa, số và ký tự đặc biệt
        </span>
      </div>
    </>
  )
}

export default RegisterFields
```

FE/src/hooks/useAuth.ts
```
import { useState } from 'react'
import type { AuthStatus, AuthSubmission } from '../models/auth'
import { login, register } from '../services/authService'

function getSubmissionError(error: unknown): string {
  if (error instanceof TypeError) {
    return 'Could not connect to the server. Check that the backend is running and try again.'
  }

  if (error instanceof Error) {
    return error.message
  }

  return 'Something went wrong. Please try again.'
}

export function useAuth() {
  const [status, setStatus] = useState<AuthStatus | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  async function submit(submission: AuthSubmission): Promise<void> {
    setStatus(null)
    setIsSubmitting(true)

    try {
      if (submission.mode === 'login') {
        const response = await login(submission.data)

        setStatus({
          kind: 'login-success',
          message: response.message,
          user: response.user,
        })
      } else {
        const user = await register(submission.data)
        setStatus({ kind: 'register-success', user })
      }
    } catch (error) {
      setStatus({ kind: 'error', message: getSubmissionError(error) })
    } finally {
      setIsSubmitting(false)
    }
  }

  function clearStatus() {
    setStatus(null)
  }

  return { status, isSubmitting, submit, clearStatus }
}
```

FE/src/models/auth.ts
```
export type AuthMode = 'login' | 'register'

export type User = {
  id: number
  username: string
  email: string
}

export type LoginRequest = {
  login: string
  password: string
}

export type RegisterRequest = {
  username: string
  password: string
  email: string
}

export type LoginResponse = {
  message: string
  access_token: string
  token_type: string
  user: User
}

export type AuthSubmission =
  | { mode: 'login'; data: LoginRequest }
  | { mode: 'register'; data: RegisterRequest }

export type AuthStatus =
  | { kind: 'error'; message: string }
  | { kind: 'login-success'; message: string; user: User }
  | { kind: 'register-success'; user: User }
```

FE/src/services/authService.ts
```
import type {
  LoginRequest,
  LoginResponse,
  RegisterRequest,
  User,
} from '../models/auth'

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function isUser(value: unknown): value is User {
  if (!isRecord(value)) {
    return false
  }

  return (
    typeof value.id === 'number' &&
    typeof value.username === 'string' &&
    typeof value.email === 'string'
  )
}

function isLoginResponse(value: unknown): value is LoginResponse {
  if (!isRecord(value)) {
    return false
  }

  return (
    typeof value.message === 'string' &&
    typeof value.access_token === 'string' &&
    typeof value.token_type === 'string' &&
    isUser(value.user)
  )
}

function getErrorMessage(payload: unknown, status: number): string {
  if (isRecord(payload) && 'detail' in payload) {
    const { detail } = payload

    if (typeof detail === 'string') {
      return detail
    }

    if (Array.isArray(detail)) {
      const messages = detail.flatMap((item) =>
        isRecord(item) && typeof item.msg === 'string' ? [item.msg] : [],
      )

      if (messages.length > 0) {
        return messages.join(' ')
      }
    }
  }

  return `Request failed with status ${status}. Please try again.`
}

async function postJson(
  path: string,
  body: LoginRequest | RegisterRequest,
): Promise<unknown> {
  const response = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })

  let payload: unknown

  try {
    payload = await response.json()
  } catch {
    throw new Error('The server returned an invalid response.')
  }

  if (!response.ok) {
    throw new Error(getErrorMessage(payload, response.status))
  }

  return payload
}

export async function login(data: LoginRequest): Promise<LoginResponse> {
  const payload = await postJson('/api/login', data)

  if (!isLoginResponse(payload)) {
    throw new Error('The server returned an unexpected login response.')
  }

  return payload
}

export async function register(data: RegisterRequest): Promise<User> {
  const payload = await postJson('/api/register', data)

  if (!isUser(payload)) {
    throw new Error('The server returned an unexpected registration response.')
  }

  return payload
}
```

</source_code>