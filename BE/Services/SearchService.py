"""Accent-insensitive search (small catalog; prefer DB full-text for very large datasets)."""
from fastapi import HTTPException
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session
from Models.Algorithms import Algorithm
from Repositories.InteractionRepository import InteractionRepository
from Services.ContentHelpers import algorithm_out, normalized


class SearchService:
    def __init__(self,db:Session):
        self.db=db
        self.interactions=InteractionRepository(db)

    def search(self,q,page,page_size,category_id=None,difficulty=None):
        term=normalized(q.strip())
        if len(term)<1:raise HTTPException(400,'Từ khóa tìm kiếm không được trống')
        stmt=select(Algorithm).where(Algorithm.is_deleted.is_(False),Algorithm.search_key.contains(term, autoescape=True))
        if category_id is not None:stmt=stmt.where(Algorithm.category_id==category_id)
        if difficulty:stmt=stmt.where(Algorithm.difficulty==difficulty)
        total=self.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        # Prefix matches prioritized; matchedIn is derived, not a persisted field.
        ordered=stmt.order_by(case((Algorithm.search_key.startswith(term),0),else_=1),Algorithm.name.asc(),Algorithm.id.asc())
        rows=self.db.scalars(ordered.offset((page-1)*page_size).limit(page_size)).all()
        data=[]
        stats=self.interactions.bulk_rating_stats([a.id for a in rows])
        for a in rows:
            item=algorithm_out(a,self.interactions,rating=stats.get(a.id,(0.0,0)))
            item['matched_in']='name' if term in normalized(a.name) else ('summary' if term in normalized(a.summary) else 'tag')
            data.append(item)
        return {'data':data,'meta':{'page':page,'page_size':page_size,'total':total}}

    def suggest(self,q,limit):
        term=normalized(q.strip())
        if not term:return []
        stmt=(select(Algorithm).where(Algorithm.is_deleted.is_(False),Algorithm.search_key.contains(term, autoescape=True))
             .order_by(case((Algorithm.search_key.startswith(term),0),else_=1),Algorithm.name.asc()).limit(limit))
        return [{'slug':a.slug,'name':a.name} for a in self.db.scalars(stmt)]
