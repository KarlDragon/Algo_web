from datetime import datetime
from html import escape
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from Models.Algorithms import Algorithm
from Models.Interaction import Comment,Rating,Favorite,LearningProgress
from Models.Users import User
from Repositories.InteractionRepository import InteractionRepository
from Services.AlgorithmService import AlgorithmService
from Services.ContentHelpers import algorithm_out,comment_out
from Models.Algorithms import now_utc
from Services.HomeCache import invalidate as invalidate_home


class InteractionService:
    def __init__(self,db:Session):
        self.db=db
        self.repo=InteractionRepository(db)
        self.algos=AlgorithmService(db)

    def _algorithm(self,id):
        return self.algos.require_algorithm(id)

    def _comment(self,id):
        obj=self.repo.get_comment(id)
        if obj is None:raise HTTPException(404,'Không tìm thấy bình luận')
        return obj

    def list_comments(self,algorithm_id,user_id,page,page_size,sort,parent_id=None):
        self._algorithm(algorithm_id)
        if parent_id is not None:
            parent=self._comment(parent_id)
            if parent.algorithm_id!=algorithm_id:raise HTTPException(404,'Bình luận không thuộc thuật toán này')
        rows,total=self.repo.comments(algorithm_id,page,page_size,sort,parent_id)
        counts=self.repo.reply_counts([c.id for c in rows])
        return {'data':[comment_out(c,self.repo,user_id,counts.get(c.id,0)) for c in rows],
                'meta':{'page':page,'page_size':page_size,'total':total}}

    def add_comment(self,algorithm_id,user:User,data):
        self._algorithm(algorithm_id)
        if data.parent_id is not None:
            parent=self._comment(data.parent_id)
            if parent.algorithm_id!=algorithm_id:raise HTTPException(400,'Bình luận cha phải thuộc cùng thuật toán')
            if parent.parent_id is not None:raise HTTPException(400,'Chỉ hỗ trợ trả lời bình luận gốc')
        c=Comment(algorithm_id=algorithm_id,user_id=user.id,parent_id=data.parent_id,content=escape(data.content, quote=True))
        self.db.add(c);self.db.commit();self.db.refresh(c)
        return comment_out(c,self.repo,user.id)

    def update_comment(self,id,user:User,data):
        obj=self._comment(id)
        if obj.user_id!=user.id:raise HTTPException(403,'Bạn không thể sửa bình luận của người khác')
        obj.content=escape(data.content.strip(), quote=True)
        if not obj.content:raise HTTPException(400,'Bình luận không được để trống')
        obj.updated_at=now_utc()
        self.db.commit()
        return comment_out(obj,self.repo,user.id)

    def delete_comment(self,id,user:User):
        obj=self._comment(id)
        if obj.user_id!=user.id and user.role!='ADMIN':raise HTTPException(403,'Bạn không thể xóa bình luận này')
        # ORM cascades replies within the transaction; SQLite FK cascade is enabled too.
        self.db.delete(obj);self.db.commit()

    def stats(self,algorithm_id,user_id):
        self._algorithm(algorithm_id)
        avg,count=self.repo.rating_stats(algorithm_id)
        mine=self.repo.rating(user_id,algorithm_id)
        return {'avg_rating':avg,'rating_count':count,'my_score':mine.score if mine else None,
                'distribution':self.repo.rating_distribution(algorithm_id)}

    def set_rating(self,algorithm_id,user_id,score):
        self._algorithm(algorithm_id)
        row=self.repo.rating(user_id,algorithm_id)
        if row is None:self.db.add(Rating(algorithm_id=algorithm_id,user_id=user_id,score=score))
        else:row.score=score;row.updated_at=now_utc()
        self.db.commit();invalidate_home()
        return self.stats(algorithm_id,user_id)

    def delete_rating(self,algorithm_id,user_id):
        self._algorithm(algorithm_id)
        obj=self.repo.rating(user_id,algorithm_id)
        if obj is None:raise HTTPException(404,'Bạn chưa đánh giá thuật toán này')
        self.db.delete(obj);self.db.commit();invalidate_home()

    def set_favorite(self,algorithm_id,user_id):
        self._algorithm(algorithm_id)
        if not self.repo.favorite(user_id,algorithm_id):
            self.db.add(Favorite(user_id=user_id,algorithm_id=algorithm_id))
            self.db.commit()
        return {'message':'Đã lưu thuật toán yêu thích'}

    def delete_favorite(self,algorithm_id,user_id):
        obj=self.repo.favorite(user_id,algorithm_id)
        if obj is None:raise HTTPException(404,'Thuật toán chưa nằm trong danh sách yêu thích')
        self.db.delete(obj);self.db.commit()

    def favorites(self,user_id,page,page_size):
        from sqlalchemy import func
        stmt=(select(Algorithm).join(Favorite,Favorite.algorithm_id==Algorithm.id)
              .where(Favorite.user_id==user_id,Algorithm.is_deleted.is_(False))
              .order_by(Favorite.created_at.desc(),Favorite.id.desc()))
        total=self.db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
        rows=self.db.scalars(stmt.offset((page-1)*page_size).limit(page_size)).all()
        return {'data':[algorithm_out(a,self.repo) for a in rows], 'meta':{'page':page,'page_size':page_size,'total':total}}

    def get_progress(self,algorithm_id,user_id):
        self._algorithm(algorithm_id)
        obj=self.repo.progress(user_id,algorithm_id)
        if obj is None:return {'algorithm_id':algorithm_id,'status':'NOT_STARTED','progress_percent':0,'last_viewed_at':None,'completed_at':None}
        return {'algorithm_id':algorithm_id,'status':obj.status,'progress_percent':obj.progress_percent,
                'last_viewed_at':obj.last_viewed_at,'completed_at':obj.completed_at}

    def set_progress(self,algorithm_id,user_id,data):
        self._algorithm(algorithm_id)
        obj=self.repo.progress(user_id,algorithm_id)
        if obj is None:
            obj=LearningProgress(user_id=user_id,algorithm_id=algorithm_id);self.db.add(obj)
        obj.status=data.status;obj.progress_percent=data.progress_percent;obj.last_viewed_at=now_utc()
        if data.status=='COMPLETED':
            if data.progress_percent!=100:raise HTTPException(400,'Đã hoàn thành phải đạt 100%')
            obj.completed_at=now_utc()
        else:obj.completed_at=None
        self.db.commit()
        return self.get_progress(algorithm_id,user_id)
