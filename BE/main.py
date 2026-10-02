from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from Services.Register import register_user


app = FastAPI()


class RegisterRequest(BaseModel):
    username: str
    password: str
    email: str


@app.get("/")
def home():
    return {
        "message": "Backend is running"
    }


@app.post("/register", status_code=201)
def register(data: RegisterRequest):

    user = register_user(
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