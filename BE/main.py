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