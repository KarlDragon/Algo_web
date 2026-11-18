"""Persistence model for content, search and learning features."""
from datetime import datetime, timezone
from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from Models.Base import Base


def now_utc():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Category(Base):
    __tablename__ = 'categories'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(140), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=now_utc, nullable=False)


class Algorithm(Base):
    __tablename__ = 'algorithms'
    id: Mapped[int] = mapped_column(primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey('categories.id', ondelete='RESTRICT'), index=True)
    slug: Mapped[str] = mapped_column(String(150), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    difficulty: Mapped[str] = mapped_column(String(10), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    theory: Mapped[str] = mapped_column(Text, nullable=False)
    pseudocode: Mapped[str] = mapped_column(Text, nullable=False)
    time_best: Mapped[str] = mapped_column(String(60), nullable=False)
    time_average: Mapped[str] = mapped_column(String(60), nullable=False)
    time_worst: Mapped[str] = mapped_column(String(60), nullable=False)
    space_complexity: Mapped[str] = mapped_column(String(60), nullable=False)
    has_simulation: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text('0'))
    search_key: Mapped[str] = mapped_column(Text, nullable=False, default='')
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=now_utc, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(), default=now_utc, onupdate=now_utc, nullable=False)
    category: Mapped['Category'] = relationship()
    code_samples: Mapped[list['CodeSample']] = relationship(back_populates='algorithm', cascade='all, delete-orphan', lazy='selectin')
    tags: Mapped[list['Tag']] = relationship(secondary='algorithm_tags', lazy='selectin')
    examples: Mapped[list['AlgorithmExample']] = relationship(cascade='all, delete-orphan', lazy='selectin')
    diagrams: Mapped[list['AlgorithmDiagram']] = relationship(cascade='all, delete-orphan', lazy='selectin')
    visualization_config: Mapped['VisualizationConfig | None'] = relationship(cascade='all, delete-orphan', uselist=False, lazy='selectin')
    __table_args__=(CheckConstraint("difficulty IN ('EASY','MEDIUM','HARD')",name='ck_algorithms_difficulty'), Index('ix_algorithms_search_key','search_key'))


class CodeSample(Base):
    __tablename__ = 'code_samples'
    id: Mapped[int] = mapped_column(primary_key=True)
    algorithm_id: Mapped[int] = mapped_column(ForeignKey('algorithms.id', ondelete='CASCADE'), nullable=False, index=True)
    language: Mapped[str] = mapped_column(String(30), nullable=False)
    code: Mapped[str] = mapped_column(Text, nullable=False)
    algorithm: Mapped['Algorithm'] = relationship(back_populates='code_samples')
    __table_args__ = (UniqueConstraint('algorithm_id','language',name='uq_code_sample_language'),)


class Tag(Base):
    __tablename__ = 'tags'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)


class AlgorithmTag(Base):
    __tablename__ = 'algorithm_tags'
    algorithm_id: Mapped[int] = mapped_column(ForeignKey('algorithms.id', ondelete='CASCADE'), primary_key=True)
    tag_id: Mapped[int] = mapped_column(ForeignKey('tags.id', ondelete='CASCADE'), primary_key=True)


class AlgorithmExample(Base):
    __tablename__ = 'algorithm_examples'
    id: Mapped[int] = mapped_column(primary_key=True)
    algorithm_id: Mapped[int] = mapped_column(ForeignKey('algorithms.id', ondelete='CASCADE'), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    input_data: Mapped[str] = mapped_column(Text, nullable=False)
    expected_output: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class AlgorithmDiagram(Base):
    __tablename__ = 'algorithm_diagrams'
    id: Mapped[int] = mapped_column(primary_key=True)
    algorithm_id: Mapped[int] = mapped_column(ForeignKey('algorithms.id', ondelete='CASCADE'), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    diagram_type: Mapped[str] = mapped_column(String(30), nullable=False)
    source_text: Mapped[str | None] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(String(500))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class VisualizationConfig(Base):
    __tablename__ = 'visualization_configs'
    id: Mapped[int] = mapped_column(primary_key=True)
    algorithm_id: Mapped[int] = mapped_column(ForeignKey('algorithms.id', ondelete='CASCADE'), nullable=False, unique=True)
    renderer_key: Mapped[str] = mapped_column(String(80), nullable=False)
    config_json: Mapped[str] = mapped_column(Text, nullable=False, default='{}')


class HomeBanner(Base):
    __tablename__ = 'home_banners'
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    image_url: Mapped[str] = mapped_column(String(500), nullable=False)
    link_url: Mapped[str] = mapped_column(String(500), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
