"""Pydantic schemas for Swagger/OpenAPI and response validation.

Response names and snake_case keys intentionally match the existing FE/BE contract.
"""
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    detail: str


class MessageResponse(BaseModel):
    message: str


class RegisterResponse(BaseModel):
    id: int
    username: str
    email: str
    role: Literal['USER', 'ADMIN']


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int
    token_type: str


class LoginResponse(TokenResponse):
    message: str
    user: RegisterResponse


class UserResponse(RegisterResponse):
    full_name: str | None
    avatar_url: str | None
    created_at: datetime


class PageMeta(BaseModel):
    page: int
    page_size: int
    total: int


class UserPage(BaseModel):
    data: list[UserResponse]
    meta: PageMeta


class CategoryResponse(BaseModel):
    id: int
    name: str
    slug: str
    description: str | None
    algorithm_count: int | None = None


class AlgorithmSummary(BaseModel):
    id: int
    slug: str
    name: str
    summary: str
    category: str
    category_id: int
    difficulty: Literal['EASY', 'MEDIUM', 'HARD']
    avg_rating: float
    rating_count: int
    has_simulation: bool


class AlgorithmPage(BaseModel):
    data: list[AlgorithmSummary]
    meta: PageMeta


class SearchMatch(AlgorithmSummary):
    matched_in: Literal['name', 'summary', 'tag']


class SearchPage(BaseModel):
    data: list[SearchMatch]
    meta: PageMeta


class SearchSuggestion(BaseModel):
    slug: str
    name: str


class CodeSampleResponse(BaseModel):
    id: int
    language: str
    code: str


class ComplexityResponse(BaseModel):
    time_best: str
    time_average: str
    time_worst: str
    space: str


class TagResponse(BaseModel):
    id: int
    name: str
    slug: str


class ExampleResponse(BaseModel):
    id: int
    title: str
    input_data: str
    expected_output: str
    explanation: str
    sort_order: int


class DiagramResponse(BaseModel):
    id: int
    title: str
    diagram_type: str
    source_text: str | None
    image_url: str | None
    sort_order: int


class VisualizationResponse(BaseModel):
    renderer_key: str
    config_json: str


class AlgorithmDetail(AlgorithmSummary):
    theory: str
    pseudocode: str
    code_samples: list[CodeSampleResponse]
    complexity: ComplexityResponse
    tags: list[TagResponse]
    examples: list[ExampleResponse]
    diagrams: list[DiagramResponse]
    visualization_config: VisualizationResponse | None
    comment_count: int
    created_at: datetime
    updated_at: datetime


class BannerResponse(BaseModel):
    id: int
    title: str
    image_url: str
    link_url: str
    sort_order: int
    is_active: bool


class HomeIntro(BaseModel):
    title: str
    description: str


class HomeStats(BaseModel):
    algorithms: int
    users: int


class HomeResponse(BaseModel):
    intro: HomeIntro
    banners: list[BannerResponse]
    featured_algorithms: list[AlgorithmSummary]
    categories: list[CategoryResponse]
    stats: HomeStats


class CommentAuthor(BaseModel):
    id: int
    username: str
    avatar_url: str | None


class CommentResponse(BaseModel):
    id: int
    content: str
    author: CommentAuthor
    algorithm_id: int
    parent_id: int | None
    reply_count: int
    created_at: datetime
    updated_at: datetime
    is_mine: bool


class CommentPage(BaseModel):
    data: list[CommentResponse]
    meta: PageMeta


class RatingResponse(BaseModel):
    avg_rating: float
    rating_count: int
    my_score: int | None
    distribution: dict[str, int]


class FavoritePage(AlgorithmPage):
    pass


class ProgressResponse(BaseModel):
    algorithm_id: int
    status: Literal['NOT_STARTED', 'IN_PROGRESS', 'COMPLETED']
    progress_percent: int = Field(ge=0, le=100)
    last_viewed_at: datetime | None
    completed_at: datetime | None


class HistoryItem(BaseModel):
    algorithm: AlgorithmSummary
    status: Literal['NOT_STARTED', 'IN_PROGRESS', 'COMPLETED']
    progress_percent: int = Field(ge=0, le=100)
    last_viewed_at: datetime
    completed_at: datetime | None


class HistoryPage(BaseModel):
    data: list[HistoryItem]
    meta: PageMeta


class CompareItem(AlgorithmSummary):
    complexity: ComplexityResponse
    tags: list[TagResponse]


class CompareResponse(BaseModel):
    algorithms: list[CompareItem]
