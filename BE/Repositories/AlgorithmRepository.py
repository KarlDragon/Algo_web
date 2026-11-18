from sqlalchemy import func, select
from sqlalchemy.orm import Session
from Models.Algorithms import Algorithm, Category, HomeBanner, Tag


class AlgorithmRepository:
    def __init__(self, db: Session):
        self.db=db

    def get(self, identifier: str | int, include_deleted: bool=False):
        if isinstance(identifier,int) or str(identifier).isdigit():
            stmt=select(Algorithm).where(Algorithm.id==int(identifier))
        else:
            stmt=select(Algorithm).where(Algorithm.slug==identifier)
        if not include_deleted:
            stmt=stmt.where(Algorithm.is_deleted.is_(False))
        return self.db.scalar(stmt)

    def list(self, page, page_size, category_id=None, difficulty=None, sort='name'):
        stmt=select(Algorithm).where(Algorithm.is_deleted.is_(False))
        if category_id is not None:
            stmt=stmt.where(Algorithm.category_id==category_id)
        if difficulty:
            stmt=stmt.where(Algorithm.difficulty==difficulty)
        count=self.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        if sort=='newest': stmt=stmt.order_by(Algorithm.created_at.desc(),Algorithm.id.desc())
        else: stmt=stmt.order_by(Algorithm.name.asc(),Algorithm.id.asc())
        return self.db.scalars(stmt.offset((page-1)*page_size).limit(page_size)).all(),count

    def category_by_id(self, category_id):
        return self.db.get(Category,category_id)

    def categories(self):
        return self.db.scalars(select(Category).order_by(Category.name.asc())).all()

    def slug_exists(self, slug, exclude_id=None):
        stmt=select(Algorithm.id).where(Algorithm.slug==slug)
        if exclude_id:stmt=stmt.where(Algorithm.id != exclude_id)
        return self.db.scalar(stmt) is not None

    def category_slug_exists(self,slug,exclude_id=None):
        stmt=select(Category.id).where(Category.slug==slug)
        if exclude_id:stmt=stmt.where(Category.id!=exclude_id)
        return self.db.scalar(stmt) is not None

    def get_tag(self,slug):
        return self.db.scalar(select(Tag).where(Tag.slug==slug))

    def banners(self):
        return self.db.scalars(select(HomeBanner).where(HomeBanner.is_active.is_(True)).order_by(HomeBanner.sort_order,HomeBanner.id)).all()
