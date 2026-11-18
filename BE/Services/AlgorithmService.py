from fastapi import HTTPException
import bleach
from sqlalchemy import func, select, and_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from Models.Algorithms import (Algorithm,AlgorithmDiagram,AlgorithmExample,Category,CodeSample,
                               Tag,VisualizationConfig,HomeBanner)
from Repositories.AlgorithmRepository import AlgorithmRepository
from Repositories.InteractionRepository import InteractionRepository
from Services.ContentHelpers import algorithm_out,category_out,banner_out,normalized,slugify
from Services.HomeCache import invalidate as invalidate_home, get_or_build


class AlgorithmService:
    RESERVED_CATEGORY_SLUGS={
        'algorithm','algorithms','search','favorites','profile','history','compare','quiz'
    }

    def __init__(self,db:Session):
        self.db=db
        self.repo=AlgorithmRepository(db)
        self.interactions=InteractionRepository(db)

    def require_algorithm(self, identifier):
        alg=self.repo.get(identifier)
        if alg is None:raise HTTPException(404,'Không tìm thấy thuật toán')
        return alg

    def get_categories(self):
        return get_or_build(self._get_categories_uncached, key='categories')

    def _get_categories_uncached(self):
        rows=self.db.execute(select(Category,func.count(Algorithm.id))
                 .outerjoin(Algorithm,and_(Algorithm.category_id==Category.id,Algorithm.is_deleted.is_(False)))
                 .group_by(Category.id).order_by(Category.name)).all()
        return [category_out(c,int(count)) for c,count in rows]

    def create_category(self,data):
        if data.slug in self.RESERVED_CATEGORY_SLUGS:
            raise HTTPException(400,'Slug danh mục bị trùng với đường dẫn hệ thống')
        if self.repo.category_slug_exists(data.slug):raise HTTPException(409,'Slug danh mục đã tồn tại')
        c=Category(**data.model_dump())
        self.db.add(c)
        try:self.db.commit();invalidate_home()
        except IntegrityError:
            self.db.rollback();raise HTTPException(409,'Danh mục đã tồn tại')
        self.db.refresh(c)
        return category_out(c,0)

    def update_category(self,id,data):
        c=self.repo.category_by_id(id)
        if c is None:raise HTTPException(404,'Không tìm thấy danh mục')
        if data.slug in self.RESERVED_CATEGORY_SLUGS:
            raise HTTPException(400,'Slug danh mục bị trùng với đường dẫn hệ thống')
        if self.repo.category_slug_exists(data.slug,id):raise HTTPException(409,'Slug danh mục đã tồn tại')
        for k,v in data.model_dump().items():setattr(c,k,v)
        try:self.db.commit();invalidate_home()
        except IntegrityError:
            self.db.rollback();raise HTTPException(409,'Danh mục đã tồn tại')
        return category_out(c)

    def delete_category(self,id):
        c=self.repo.category_by_id(id)
        if c is None:raise HTTPException(404,'Không tìm thấy danh mục')
        if self.db.scalar(select(func.count(Algorithm.id)).where(Algorithm.category_id==id)):
            raise HTTPException(409,'Danh mục còn chứa thuật toán, không thể xóa')
        self.db.delete(c);self.db.commit();invalidate_home()

    def list_algorithms(self,page,page_size,category_id,difficulty,sort):
        cache_key=f'algorithms:{page}:{page_size}:{category_id}:{difficulty}:{sort}'
        return get_or_build(lambda:self._list_algorithms_uncached(page,page_size,category_id,difficulty,sort),
                            key=cache_key)

    def _list_algorithms_uncached(self,page,page_size,category_id,difficulty,sort):
        # Sorting by rating uses an aggregated query, not an N+1 Python in-memory sort.
        if sort=='rating':
            from Models.Interaction import Rating
            stmt=(select(Algorithm).outerjoin(Rating,Rating.algorithm_id==Algorithm.id)
               .where(Algorithm.is_deleted.is_(False)).group_by(Algorithm.id)
               .order_by(func.coalesce(func.avg(Rating.score),0).desc(),Algorithm.name.asc()))
            if category_id is not None:stmt=stmt.where(Algorithm.category_id==category_id)
            if difficulty:stmt=stmt.where(Algorithm.difficulty==difficulty)
            total=self.db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
            rows=self.db.scalars(stmt.offset((page-1)*page_size).limit(page_size)).all()
        else:rows,total=self.repo.list(page,page_size,category_id,difficulty,sort)
        stats=self.interactions.bulk_rating_stats([a.id for a in rows])
        return {'data':[algorithm_out(a,self.interactions,rating=stats.get(a.id,(0.0,0))) for a in rows],
                'meta':{'page':page,'page_size':page_size,'total':total}}

    def get_algorithm(self,identifier):
        return algorithm_out(self.require_algorithm(identifier),self.interactions,True)

    def compare(self,ids_csv):
        identifiers=[]
        for value in ids_csv.split(','):
            identifier=value.strip()
            if identifier and identifier not in identifiers:
                identifiers.append(identifier)
        if not 2<=len(identifiers)<=4:
            raise HTTPException(400,'Cần chọn từ 2 đến 4 thuật toán để so sánh')
        algorithms=[]
        for identifier in identifiers:
            try:
                algorithms.append(self.require_algorithm(identifier))
            except HTTPException as exc:
                if exc.status_code==404:
                    raise HTTPException(404,f'Không tìm thấy thuật toán: {identifier}') from exc
                raise
        stats=self.interactions.bulk_rating_stats([algorithm.id for algorithm in algorithms])
        result=[]
        for algorithm in algorithms:
            detailed=algorithm_out(
                algorithm,self.interactions,True,
                stats.get(algorithm.id,(0.0,0)),
            )
            result.append({
                key:detailed[key] for key in (
                    'id','slug','name','summary','category','category_id','difficulty',
                    'avg_rating','rating_count','has_simulation','complexity','tags',
                )
            })
        return {'algorithms':result}

    def _assign(self,alg,data):
        for k in ('slug','category_id','difficulty','name','summary','theory','pseudocode','has_simulation'):
            setattr(alg,k,getattr(data,k))
        for k,v in data.complexity.items():setattr(alg,'space_complexity' if k=='space' else k,v)
        # Admin-authored HTML is allowed only with safe formatting tags.
        # Code samples and pseudocode are intentionally NOT sanitized as HTML.
        html_tags=['p','br','strong','em','b','i','ul','ol','li','blockquote','pre','code',
                   'h1','h2','h3','h4','a']
        allowed_attrs={'a':['href','title']}
        alg.theory=bleach.clean(data.theory,tags=html_tags,attributes=allowed_attrs,
                                protocols=['http','https'],strip=True)
        alg.summary=bleach.clean(data.summary,tags=[],strip=True)
        alg.name=bleach.clean(data.name,tags=[],strip=True)
        alg.search_key=normalized(alg.name+' '+alg.summary+' '+' '.join(data.tags))
        # Reuse matching rows so PUT does not violate UNIQUE(algorithm_id, language)
        # through insert-before-delete SQLAlchemy flush ordering.
        current={x.language:x for x in alg.code_samples}
        samples=[]
        for item in data.code_samples:
            language=item.language.strip().lower()
            obj=current.get(language)
            if obj is None:obj=CodeSample(language=language,code=item.code)
            else:obj.code=item.code
            samples.append(obj)
        alg.code_samples=samples
        alg.examples=[AlgorithmExample(**e.model_dump()) for e in data.examples]
        alg.diagrams=[AlgorithmDiagram(**d.model_dump()) for d in data.diagrams]
        if data.visualization_config is None:
            alg.visualization_config=None
        elif alg.visualization_config is None:
            alg.visualization_config=VisualizationConfig(**data.visualization_config.model_dump())
        else:
            alg.visualization_config.renderer_key=data.visualization_config.renderer_key
            alg.visualization_config.config_json=data.visualization_config.config_json
        tags=[]
        for raw in data.tags:
            slug=slugify(raw)
            if not slug:raise HTTPException(400,'Thẻ không hợp lệ')
            tag=self.repo.get_tag(slug)
            if tag is None:
                tag=Tag(name=raw.strip(),slug=slug)
                self.db.add(tag)
                self.db.flush()
            if tag not in tags:tags.append(tag)
        alg.tags=tags

    def save_algorithm(self,data,alg=None):
        if not self.repo.category_by_id(data.category_id):raise HTTPException(400,'Danh mục không tồn tại')
        if self.repo.slug_exists(data.slug,alg.id if alg else None):raise HTTPException(409,'Slug thuật toán đã tồn tại')
        if alg is None:
            alg=Algorithm();self.db.add(alg)
        self._assign(alg,data)
        try:self.db.commit();invalidate_home()
        except IntegrityError:
            self.db.rollback();raise HTTPException(409,'Dữ liệu thuật toán bị trùng')
        self.db.refresh(alg)
        return algorithm_out(alg,self.interactions,True)

    def soft_delete(self,id):
        alg=self.require_algorithm(id)
        alg.is_deleted=True
        self.db.commit();invalidate_home()

    def banners(self):
        return [banner_out(x) for x in self.repo.banners()]

    def create_banner(self,data):
        b=HomeBanner(**data.model_dump());self.db.add(b);self.db.commit();invalidate_home();self.db.refresh(b)
        return banner_out(b)

    def change_banner(self,id,data):
        b=self.db.get(HomeBanner,id)
        if b is None:raise HTTPException(404,'Banner không tồn tại')
        for k,v in data.model_dump().items():setattr(b,k,v)
        self.db.commit();invalidate_home();return banner_out(b)

    def delete_banner(self,id):
        b=self.db.get(HomeBanner,id)
        if b is None:raise HTTPException(404,'Banner không tồn tại')
        self.db.delete(b);self.db.commit();invalidate_home()
