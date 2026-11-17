from typing import Literal
from html import escape
from urllib.parse import urlsplit
from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictInput(BaseModel):
    model_config = ConfigDict(extra='forbid')


def safe_link(value: str | None):
    if not value:
        return value
    if any(c in value for c in ('\\','\n','\r','\t')):
        raise ValueError('Đường dẫn không hợp lệ')
    parsed = urlsplit(value)
    absolute = parsed.scheme in ('http', 'https') and bool(parsed.netloc) and not (parsed.username or parsed.password)
    relative = value.startswith('/') and not value.startswith('//')
    if not (absolute or relative):
        raise ValueError('Đường dẫn phải là URL http(s) hoặc đường dẫn nội bộ bắt đầu bằng /')
    return value


class CodeSampleInput(StrictInput):
    language: str = Field(min_length=1, max_length=30)
    code: str = Field(min_length=1, max_length=100000)


class ExampleInput(StrictInput):
    title: str = Field(min_length=1, max_length=160)
    input_data: str
    expected_output: str
    explanation: str
    sort_order: int = 0


class DiagramInput(StrictInput):
    title: str = Field(min_length=1, max_length=160)
    diagram_type: str = Field(min_length=1, max_length=30)
    source_text: str | None = None
    image_url: str | None = Field(default=None, max_length=500)
    sort_order: int = 0

    @field_validator('image_url')
    @classmethod
    def safe_diagram_image(cls, v):
        return safe_link(v)


class VisualizationInput(StrictInput):
    renderer_key: str = Field(min_length=1, max_length=80)
    config_json: str = '{}'

    @field_validator('config_json')
    @classmethod
    def valid_json(cls, value):
        import json
        try:
            obj=json.loads(value)
        except json.JSONDecodeError:
            raise ValueError('Cấu hình mô phỏng không phải JSON hợp lệ')
        if not isinstance(obj,dict):
            raise ValueError('Cấu hình mô phỏng phải là JSON object')
        return value


class CategoryInput(StrictInput):
    name: str = Field(min_length=1, max_length=120)
    slug: str = Field(pattern=r'^[a-z0-9]+(?:-[a-z0-9]+)*$', min_length=2, max_length=140)
    description: str | None = None


class AlgorithmInput(StrictInput):
    slug: str = Field(pattern=r'^[a-z0-9]+(?:-[a-z0-9]+)*$', min_length=2, max_length=150)
    category_id: int = Field(ge=1)
    difficulty: Literal['EASY','MEDIUM','HARD']
    name: str = Field(min_length=2, max_length=160)
    summary: str = Field(min_length=1, max_length=2000)
    theory: str = Field(min_length=1, max_length=200000)
    pseudocode: str = Field(min_length=1, max_length=50000)
    code_samples: list[CodeSampleInput] = Field(default_factory=list, max_length=30)
    complexity: dict[Literal['time_best','time_average','time_worst','space'],str]
    has_simulation: bool = False
    tags: list[str] = Field(default_factory=list)
    examples: list[ExampleInput] = Field(default_factory=list, max_length=50)
    diagrams: list[DiagramInput] = Field(default_factory=list, max_length=50)
    visualization_config: VisualizationInput | None = None

    @field_validator('complexity')
    @classmethod
    def valid_complexity(cls, value):
        if set(value) != {'time_best','time_average','time_worst','space'}:
            raise ValueError('Cần cung cấp đủ 4 độ phức tạp')
        if not all(str(x).strip() for x in value.values()):
            raise ValueError('Giá trị độ phức tạp không được để trống')
        return value

    @field_validator('tags')
    @classmethod
    def valid_tags(cls, value):
        if len(value) > 20 or any(not t.strip() or len(t)>80 for t in value):
            raise ValueError('Danh sách thẻ không hợp lệ')
        return value

    @field_validator('code_samples')
    @classmethod
    def unique_language(cls, value):
        names=[x.language.strip().lower() for x in value]
        if len(names)!=len(set(names)):
            raise ValueError('Ngôn ngữ code mẫu không được trùng')
        return value


class BannerInput(StrictInput):
    title: str = Field(min_length=1, max_length=160)
    image_url: str = Field(min_length=1, max_length=500)
    link_url: str = Field(min_length=1, max_length=500)
    sort_order: int = 0
    is_active: bool = True

    @field_validator('image_url','link_url')
    @classmethod
    def validate_safe_urls(cls, v):
        return safe_link(v)


class ProfileInput(StrictInput):
    full_name: str | None = Field(default=None, max_length=100)
    avatar_url: str | None = Field(default=None, max_length=500)

    @field_validator('avatar_url')
    @classmethod
    def validate_avatar_url(cls, v):
        return safe_link(v)


class RoleInput(StrictInput):
    role: Literal['USER','ADMIN']


class CommentInput(StrictInput):
    content: str = Field(min_length=1, max_length=1000)
    parent_id: int | None = Field(default=None, ge=1)

    @field_validator('content')
    @classmethod
    def trim_content(cls,v):
        t=v.strip()
        if not t:
            raise ValueError('Nội dung bình luận không được trống')
        if len(escape(t, quote=True)) > 1000:
            raise ValueError('Nội dung bình luận quá dài sau khi mã hóa ký tự HTML')
        return t


class CommentEditInput(StrictInput):
    content: str = Field(min_length=1,max_length=1000)

    @field_validator('content')
    @classmethod
    def trim_content(cls,v):
        t=v.strip()
        if not t:
            raise ValueError('Nội dung bình luận không được trống')
        if len(escape(t, quote=True)) > 1000:
            raise ValueError('Nội dung bình luận quá dài sau khi mã hóa ký tự HTML')
        return t


class RatingInput(StrictInput):
    score: int = Field(ge=1, le=5)


class ProgressInput(StrictInput):
    status: Literal['NOT_STARTED','IN_PROGRESS','COMPLETED']
    progress_percent: int = Field(ge=0, le=100)
