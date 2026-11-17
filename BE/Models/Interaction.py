from datetime import datetime
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from Models.Base import Base
from Models.Algorithms import now_utc


class Comment(Base):
    __tablename__ = 'comments'
    id: Mapped[int] = mapped_column(primary_key=True)
    algorithm_id: Mapped[int] = mapped_column(ForeignKey('algorithms.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey('comments.id', ondelete='CASCADE'), nullable=True, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=now_utc, onupdate=now_utc)
    author = relationship('User')
    replies: Mapped[list['Comment']] = relationship('Comment', back_populates='parent', cascade='all, delete-orphan')
    parent: Mapped['Comment | None'] = relationship('Comment', remote_side='Comment.id', back_populates='replies')
    __table_args__ = (CheckConstraint('length(content) BETWEEN 1 AND 1000',name='ck_comment_length'),)


class Rating(Base):
    __tablename__ = 'ratings'
    id: Mapped[int] = mapped_column(primary_key=True)
    algorithm_id: Mapped[int] = mapped_column(ForeignKey('algorithms.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=now_utc, onupdate=now_utc)
    __table_args__ = (UniqueConstraint('user_id','algorithm_id',name='uq_rating_user_algorithm'), CheckConstraint('score BETWEEN 1 AND 5',name='ck_rating_score'))


class Favorite(Base):
    __tablename__ = 'favorites'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    algorithm_id: Mapped[int] = mapped_column(ForeignKey('algorithms.id', ondelete='CASCADE'), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False, default=now_utc)
    __table_args__ = (UniqueConstraint('user_id','algorithm_id',name='uq_favorite_user_algorithm'),)


class LearningProgress(Base):
    __tablename__ = 'learning_progress'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    algorithm_id: Mapped[int] = mapped_column(ForeignKey('algorithms.id', ondelete='CASCADE'), nullable=False, index=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default='NOT_STARTED')
    progress_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_viewed_at: Mapped[datetime | None] = mapped_column(DateTime())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime())
    __table_args__ = (UniqueConstraint('user_id','algorithm_id',name='uq_progress_user_algorithm'), CheckConstraint('progress_percent BETWEEN 0 AND 100',name='ck_progress_percentage'), CheckConstraint("status IN ('NOT_STARTED','IN_PROGRESS','COMPLETED')",name='ck_progress_status'))
