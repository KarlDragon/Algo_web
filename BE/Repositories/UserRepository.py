from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session
from Models.Users import User


class UserRepository:
    def __init__(self, session: Session):
        self.db = session

    def find(self, user_id: int) -> User | None:
        return self.db.get(User, user_id)

    def search(self, page: int, page_size: int, q: str | None = None, role: str | None = None):
        stmt=select(User)
        if q:
            needle=f'%{q.strip()}%'
            stmt=stmt.where(or_(User.username.ilike(needle), User.email.ilike(needle)))
        if role:
            stmt=stmt.where(User.role == role)
        total=self.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        rows=self.db.scalars(stmt.order_by(User.id).offset((page-1)*page_size).limit(page_size)).all()
        return rows,total

    def number_of_admins(self):
        return self.db.scalar(select(func.count(User.id)).where(User.role == 'ADMIN')) or 0
