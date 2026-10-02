from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from Models.Users import Base, User


engine = create_engine(
    "sqlite:///users.db",
    echo=True
)   #Kết nối database


def create_user_table():    #Tạo bảng
    Base.metadata.create_all(engine)
    


def get_user_by_username(username):     #Tìm username
     with Session(engine) as session:
        statement = select(User).where(User.username == username)

        user = session.scalar(statement)

        return user

def get_user_by_email(email):     #Tìm email
    with Session(engine) as session:
        statement = select(User).where(User.email == email)

        user = session.scalar(statement)

        return user


def add_user(username, hashPassword, email):    #Thêm User
    with Session(engine) as session:

        user = User(
            username=username,
            hashPassword=hashPassword,
            email=email
        )

        session.add(user)

        try:
            session.commit()
            session.refresh(user)
            return user

        except IntegrityError:
            session.rollback()
            return None