from fastapi import FastAPI

from Controllers.AuthController import AuthController


app = FastAPI()

auth_controller = AuthController()

app.include_router(
    auth_controller.router
)