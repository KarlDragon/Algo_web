from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload
from Models.Algorithms import Algorithm
from Models.Interaction import Comment, Rating, Favorite, LearningProgress


class InteractionRepository:
    def __init__(self,db:Session):
        self.db=db

    def get_comment(self,id):
        return self.db.get(Comment,id)

    def comments(self,algorithm_id,page,page_size,sort='newest',parent_id=None):
        stmt=select(Comment).where(Comment.algorithm_id==algorithm_id,Comment.parent_id==parent_id)
        count=self.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        order=(Comment.created_at.desc(),Comment.id.desc()) if sort=='newest' else (Comment.created_at.asc(),Comment.id.asc())
        from sqlalchemy.orm import selectinload
        return self.db.scalars(stmt.options(selectinload(Comment.author)).order_by(*order).offset((page-1)*page_size).limit(page_size)).all(),count

    def reply_counts(self,ids):
        if not ids:return {}
        rows=self.db.execute(select(Comment.parent_id,func.count(Comment.id))
                        .where(Comment.parent_id.in_(ids)).group_by(Comment.parent_id)).all()
        return dict(rows)

    def reply_count(self,id):
        return self.db.scalar(select(func.count(Comment.id)).where(Comment.parent_id==id)) or 0

    def comment_count(self,algorithm_id):
        return self.db.scalar(select(func.count(Comment.id)).where(Comment.algorithm_id==algorithm_id)) or 0

    def rating(self,user_id,algorithm_id):
        return self.db.scalar(select(Rating).where(Rating.user_id==user_id,Rating.algorithm_id==algorithm_id))

    def bulk_rating_stats(self,algorithm_ids):
        if not algorithm_ids:return {}
        rows=self.db.execute(select(Rating.algorithm_id,func.count(Rating.id),func.avg(Rating.score))
                              .where(Rating.algorithm_id.in_(algorithm_ids)).group_by(Rating.algorithm_id)).all()
        return {id:(round(float(avg or 0),2),int(cnt)) for id,cnt,avg in rows}

    def rating_stats(self,algorithm_id):
        count,avg=self.db.execute(select(func.count(Rating.id),func.avg(Rating.score)).where(Rating.algorithm_id==algorithm_id)).one()
        return round(float(avg or 0),2),int(count)

    def rating_distribution(self,algorithm_id):
        rows=self.db.execute(select(Rating.score,func.count(Rating.id)).where(Rating.algorithm_id==algorithm_id).group_by(Rating.score)).all()
        return {str(score):next((c for s,c in rows if s==score),0) for score in range(1,6)}

    def favorite(self,user_id,algorithm_id):
        return self.db.scalar(select(Favorite).where(Favorite.user_id==user_id,Favorite.algorithm_id==algorithm_id))

    def progress(self,user_id,algorithm_id):
        return self.db.scalar(select(LearningProgress).where(LearningProgress.user_id==user_id,LearningProgress.algorithm_id==algorithm_id))

    def history(self,user_id,page,page_size,status=None):
        stmt=(select(LearningProgress,Algorithm)
              .join(Algorithm,Algorithm.id==LearningProgress.algorithm_id)
              .where(LearningProgress.user_id==user_id,
                     LearningProgress.last_viewed_at.is_not(None),
                     Algorithm.is_deleted.is_(False)))
        if status is not None:
            stmt=stmt.where(LearningProgress.status==status)
        total=self.db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
        rows=self.db.execute(
            stmt.options(selectinload(Algorithm.category))
                .order_by(LearningProgress.last_viewed_at.desc(),LearningProgress.id.desc())
                .offset((page-1)*page_size).limit(page_size)
        ).all()
        return rows,total
