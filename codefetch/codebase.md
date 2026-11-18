<source_code>
BE/alembic.ini
```
[alembic]
script_location = %(here)s/alembic
prepend_sys_path = %(here)s
sqlalchemy.url = sqlite:///./users.db
```

BE/database.py
```
import os
from collections.abc import Iterator
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

BASE_DIR=Path(__file__).resolve().parent
load_dotenv(BASE_DIR/'.env')
database_url=os.getenv('DATABASE_URL')
if not database_url:
    raise ValueError('DATABASE_URL không tồn tại trong BE/.env')
echo_sql=os.getenv('SQLALCHEMY_ECHO','').strip().lower() in {'1','true','yes','on'}
engine=create_engine(database_url,echo=echo_sql,pool_pre_ping=True)

if engine.dialect.name=='sqlite':
    @event.listens_for(engine,'connect')
    def _enable_sqlite_foreign_keys(dbapi_connection,connection_record):
        cursor=dbapi_connection.cursor()
        cursor.execute('PRAGMA foreign_keys=ON')
        cursor.close()

SessionLocal=sessionmaker(bind=engine,expire_on_commit=False)

def get_db()->Iterator[Session]:
    with SessionLocal() as session:
        yield session
```

BE/main.py
```
"""FastAPI entrypoint. Run Alembic upgrade before production server startup."""
import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from Controllers.AuthController import AuthController
from Controllers.UsersController import router as users_router
from Controllers.AlgorithmsController import router as algorithms_router
from Controllers.SearchController import router as search_router
from Controllers.InteractionsController import router as interactions_router
from Models.Base import Base
from Models.Users import User
from Models.AuthToken import RefreshToken,PasswordResetToken
from Models.Algorithms import Category,Algorithm,CodeSample,Tag,AlgorithmTag,AlgorithmExample,AlgorithmDiagram,VisualizationConfig,HomeBanner
from Models.Interaction import Comment,Rating,Favorite,LearningProgress
from database import engine
from Services.AuthError import AuthError

logging.basicConfig(level=os.getenv('LOG_LEVEL','INFO').upper())
logger=logging.getLogger('algoweb')

@asynccontextmanager
async def lifespan(app:FastAPI):
    # For local development only; existing databases MUST also run Alembic migrations.
    Base.metadata.create_all(bind=engine)
    yield

app=FastAPI(title='Algo_web Backend API',version='2.1.0',lifespan=lifespan)
origins=[x.strip() for x in os.getenv('CORS_ORIGINS','http://localhost:5173,http://127.0.0.1:5173').split(',') if x.strip()]
app.add_middleware(GZipMiddleware, minimum_size=1000)
if os.getenv('FORCE_HTTPS', 'false').lower() in {'1','true','yes'}:
    # Only enable behind a reverse proxy configured to send trusted HTTPS headers.
    app.add_middleware(HTTPSRedirectMiddleware)
trusted=[x.strip() for x in os.getenv('TRUSTED_HOSTS','').split(',') if x.strip()]
if trusted:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=trusted)
app.add_middleware(CORSMiddleware,allow_origins=origins,allow_methods=['GET','POST','PATCH','PUT','DELETE','OPTIONS'],
                   allow_headers=['Authorization','Content-Type'],allow_credentials=False)

@app.middleware('http')
async def request_log(request:Request,call_next):
    import time
    start=time.perf_counter()
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['X-Frame-Options']='DENY'
    response.headers['Referrer-Policy']='no-referrer'
    if request.url.scheme == 'https':
        response.headers['Strict-Transport-Security']='max-age=31536000'
    if request.url.path.startswith('/auth/') or request.url.path.startswith('/users/'):
        response.headers['Cache-Control']='no-store'
    logger.info('%s %s %s %.3fs',request.method,request.url.path,response.status_code,time.perf_counter()-start)
    return response

@app.exception_handler(AuthError)
async def auth_service_error(request: Request, exc: AuthError):
    return JSONResponse(status_code=exc.status_code, content={'detail':str(exc)})


@app.exception_handler(RequestValidationError)
async def invalid_request(request:Request,exc:RequestValidationError):
    first=exc.errors()[0] if exc.errors() else {}
    if first.get('type')=='json_invalid':message='JSON không hợp lệ'
    else:
        name=str(first.get('loc',['dữ liệu'])[-1])
        message=f'Thiếu hoặc sai định dạng trường {name}'
    return JSONResponse(status_code=400,content={'detail':message})

app.include_router(AuthController().router)
app.include_router(users_router)
app.include_router(algorithms_router)
app.include_router(search_router)
app.include_router(interactions_router)

# RequestValidationError returns 400 rather than FastAPI's default 422; publish the
# actual contract to Swagger instead of misleading FE with the 422 template.
from fastapi.openapi.utils import get_openapi


def corrected_openapi():
    if app.openapi_schema is not None:
        return app.openapi_schema
    schema = get_openapi(title=app.title, version=app.version,
                         description='API Algo_web. JSON snake_case; lỗi trả về {"detail": "..."}.',
                         routes=app.routes)
    schema.setdefault('components',{}).setdefault('schemas',{})['ValidationError400'] = {
        'type':'object','required':['detail'],
        'properties':{'detail':{'type':'string','example':'Dữ liệu không hợp lệ'}}
    }
    def error_description(code, description):
        return {'description':description,
                'content':{'application/json':{'schema':{'$ref':'#/components/schemas/ValidationError400'}}}}
    for path, operations in schema.get('paths',{}).items():
        for method, op in operations.items():
            if method not in {'get','post','put','patch','delete'} or not isinstance(op,dict):
                continue
            responses=op.get('responses',{})
            if '422' in responses:
                responses.pop('422')
                responses.setdefault('400',error_description(400,'Dữ liệu không hợp lệ'))
            if op.get('security') or path in {'/auth/login','/auth/refresh'}:
                responses.setdefault('401',error_description(401,'Chưa xác thực, token không hợp lệ hoặc hết hạn'))
            if method in {'post','put','patch','delete'} and not path.startswith('/auth/'):
                responses.setdefault('403',error_description(403,'Không có quyền thực hiện'))
            if method in {'post','put'} and (path.startswith('/algorithms') or path.startswith('/categories') or path=='/auth/register'):
                responses.setdefault('409',error_description(409,'Dữ liệu đã tồn tại'))
            if path.startswith('/auth/'):
                responses.setdefault('429',error_description(429,'Quá nhiều yêu cầu'))
    app.openapi_schema=schema
    return schema

app.openapi=corrected_openapi
```

BE/requirements-dev.txt
```
-r requirements.txt
pytest>=8,<10
httpx>=0.27,<1
```

BE/requirements-production.txt
```
-r requirements.txt
# Redis is optional in local development; required when REDIS_URL is configured.
redis>=5,<7
```

BE/requirements.txt
```
fastapi>=0.115,<1
uvicorn[standard]>=0.30,<1
SQLAlchemy>=2.0,<3
alembic>=1.13,<2
python-dotenv>=1.0,<2
pwdlib[argon2]>=0.2,<1
PyJWT>=2.8,<3
bleach>=6,<7
```

BE/seed.py
```
"""Idempotent demo data + optional explicit admin bootstrap.
Run from BE: py -m seed (after Alembic upgrade).
Never ships a hardcoded password.
"""
import os
import json
import logging
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import select
from database import SessionLocal
from Models.Users import User
from Models.Algorithms import Category, Algorithm, HomeBanner
from Schemas.ContentSchemas import AlgorithmInput,CodeSampleInput,CategoryInput,ExampleInput,DiagramInput,VisualizationInput
from Services.AlgorithmService import AlgorithmService
from Services.Register import RegisterService
from Services.ContentHelpers import slugify

load_dotenv(Path(__file__).resolve().parent/'.env')
log=logging.getLogger(__name__)

SEED_ALGOS=[
 ('bubble-sort','Bubble Sort','Sắp xếp nổi bọt','Duyệt từng cặp phần tử kề nhau và đổi chỗ nếu sai thứ tự.','EASY','O(n)','O(n²)','O(n²)','O(1)',
 '''for i from 0 to n-2:
    swapped = false
    for j from 0 to n-i-2:
        if a[j] > a[j+1]: swap(a[j],a[j+1]); swapped=true
    if not swapped: break''',
 '''def bubble_sort(a):
    a = a[:]
    for i in range(len(a)):
        swapped = False
        for j in range(len(a)-1-i):
            if a[j] > a[j+1]:
                a[j], a[j+1] = a[j+1], a[j]
                swapped = True
        if not swapped: break
    return a''', 'sorting'),
 ('selection-sort','Selection Sort','Sắp xếp chọn','Mỗi lượt chọn phần tử nhỏ nhất trong phần chưa sắp xếp và đưa lên đầu.','EASY','O(n²)','O(n²)','O(n²)','O(1)',
 '''for i in 0..n-1:
    min = i
    for j in i+1..n-1: if a[j] < a[min]: min = j
    swap(a[i],a[min])''',
 '''def selection_sort(a):
    a = a[:]
    for i in range(len(a)):
        m = min(range(i, len(a)), key=a.__getitem__)
        a[i], a[m] = a[m], a[i]
    return a''','sorting'),
 ('insertion-sort','Insertion Sort','Sắp xếp chèn','Đưa phần tử hiện tại vào đúng vị trí trong dãy đã được sắp xếp bên trái.','EASY','O(n)','O(n²)','O(n²)','O(1)',
 '''for i in 1..n-1:
    key = a[i]; j=i-1
    while j>=0 and a[j]>key: a[j+1]=a[j]; j--
    a[j+1]=key''',
 '''def insertion_sort(a):
    a = a[:]
    for i in range(1, len(a)):
        v, j = a[i], i-1
        while j >= 0 and a[j] > v:
            a[j+1] = a[j]; j -= 1
        a[j+1] = v
    return a''','sorting'),
 ('merge-sort','Merge Sort','Sắp xếp trộn','Chia mảng thành hai nửa, sắp xếp đệ quy rồi trộn hai dãy đã sắp.','MEDIUM','O(n log n)','O(n log n)','O(n log n)','O(n)',
 '''merge_sort(a):
    if len(a)<=1: return a
    split a into left,right
    return merge(merge_sort(left),merge_sort(right))''',
 '''def merge_sort(a):
    if len(a) <= 1: return a[:]
    m = len(a)//2
    l, r = merge_sort(a[:m]), merge_sort(a[m:])
    out=[]; i=j=0
    while i<len(l) and j<len(r):
        if l[i]<=r[j]:out.append(l[i]);i+=1
        else:out.append(r[j]);j+=1
    return out+l[i:]+r[j:]''','sorting'),
 ('quick-sort','Quick Sort','Sắp xếp nhanh','Chọn pivot, phân vùng mảng theo pivot rồi sắp xếp các phần đệ quy.','MEDIUM','O(n log n)','O(n log n)','O(n²)','O(n)',
 '''quick_sort(a):
    if len(a)<=1: return a
    pivot=a[len(a)//2]
    return quick_sort(<pivot) + equal(pivot) + quick_sort(>pivot)''',
 '''def quick_sort(a):
    if len(a)<=1: return a[:]
    p=a[len(a)//2]
    return quick_sort([x for x in a if x<p])+[x for x in a if x==p]+quick_sort([x for x in a if x>p])''','sorting'),
 ('binary-search','Binary Search','Tìm kiếm nhị phân','Tìm trên mảng đã sắp xếp bằng cách liên tục giảm một nửa khoảng tìm kiếm.','EASY','O(1)','O(log n)','O(log n)','O(1)',
 '''lo=0; hi=n-1
while lo<=hi:
    mid=(lo+hi)//2
    if a[mid]==target: return mid
    if a[mid]<target: lo=mid+1
    else: hi=mid-1
return -1''',
 '''def binary_search(a, target):
    lo, hi=0,len(a)-1
    while lo<=hi:
        m=(lo+hi)//2
        if a[m]==target:return m
        if a[m]<target:lo=m+1
        else:hi=m-1
    return -1''','searching'),
 ('bfs','Breadth-First Search (BFS)','Duyệt đồ thị theo chiều rộng','Dùng hàng đợi để duyệt tất cả đỉnh cách nguồn một cạnh trước khi đi xa hơn.','MEDIUM','O(V+E)','O(V+E)','O(V+E)','O(V)',
 '''queue=[start]; visited={start}
while queue:
    u=dequeue()
    for v in neighbors(u):
        if v not in visited: visited.add(v); enqueue(v)''',
 '''from collections import deque
def bfs(graph, start):
    q=deque([start]); visited={start}; order=[]
    while q:
        u=q.popleft(); order.append(u)
        for v in graph.get(u, []):
            if v not in visited:
                visited.add(v);q.append(v)
    return order''','graph'),
 ('dfs','Depth-First Search (DFS)','Duyệt đồ thị theo chiều sâu','Đi theo từng nhánh sâu nhất trước khi quay lui khám phá nhánh khác.','MEDIUM','O(V+E)','O(V+E)','O(V+E)','O(V)',
 '''dfs(u):
    mark u visited
    for v in neighbors(u):
        if v not visited: dfs(v)''',
 '''def dfs(graph, start):
    visited=set(); order=[]
    def visit(u):
        if u in visited:return
        visited.add(u);order.append(u)
        for v in graph.get(u, []):visit(v)
    visit(start)
    return order''','graph'),
 ('dijkstra','Dijkstra','Tìm đường đi ngắn nhất','Tìm đường đi ngắn nhất từ đỉnh nguồn khi trọng số cạnh không âm bằng hàng đợi ưu tiên.','HARD','O((V+E) log V)','O((V+E) log V)','O((V+E) log V)','O(V+E)',
 '''dist[source]=0; heap=[(0,source)]
while heap:
    (d,u)=pop_min()
    if d!=dist[u]: continue
    for (v,w) in adj[u]:
        if dist[v]>d+w: dist[v]=d+w; push(dist[v],v)''',
 '''import heapq
def dijkstra(g,s):
    d={v:float('inf') for v in g};d[s]=0
    pq=[(0,s)]
    while pq:
        cost,u=heapq.heappop(pq)
        if cost!=d[u]:continue
        for v,w in g.get(u,[]):
            if cost+w<d.get(v,float('inf')):
                d[v]=cost+w;heapq.heappush(pq,(d[v],v))
    return d''','graph'),
]


def seed():
    with SessionLocal() as db:
        svc=AlgorithmService(db)
        for name,slug in [('Sắp xếp','sorting'),('Tìm kiếm','searching'),('Đồ thị','graph'),('Quy hoạch động','dynamic-programming')]:
            if not db.scalar(select(Category).where(Category.slug==slug)):
                svc.create_category(CategoryInput(name=name,slug=slug,description='Kiến thức '+name.lower()+' bằng tiếng Việt'))
        categories={c.slug:c.id for c in db.scalars(select(Category))}
        created=0
        for slug,name,short,summary,level,best,avg,worst,space,pseudo,code,cat in SEED_ALGOS:
            if db.scalar(select(Algorithm).where(Algorithm.slug==slug)):
                continue
            svc.save_algorithm(AlgorithmInput(
                slug=slug,name=name,summary=summary,difficulty=level,category_id=categories[cat],
                theory=f'{short}. {summary} Hãy quan sát mô phỏng để theo dõi các bước thực hiện.',
                pseudocode=pseudo,code_samples=[CodeSampleInput(language='python',code=code)],
                complexity={'time_best':best,'time_average':avg,'time_worst':worst,'space':space},
                tags=[short,cat],has_simulation=True,
                examples=[ExampleInput(title='Ví dụ minh họa',input_data='[5, 1, 4, 2, 8]',
                                       expected_output='Tùy thuộc thuật toán',explanation=summary,sort_order=1)],
                diagrams=[DiagramInput(title='Sơ đồ tổng quan',diagram_type='mermaid',
                                       source_text='flowchart TD\n  A[Bắt đầu] --> B[Thực hiện thuật toán]\n  B --> C[Kết thúc]',sort_order=1)],
                visualization_config=VisualizationInput(renderer_key=slug,config_json=json.dumps({'speed':1,'showSteps':True}))))
            created+=1
        if not db.scalar(select(HomeBanner.id)):
            db.add(HomeBanner(title='Khám phá thuật toán',image_url='/assets/algoweb-banner.svg',
                              link_url='/algorithms/bubble-sort',sort_order=1,is_active=True))
            db.commit()
        username=os.getenv('SEED_ADMIN_USERNAME','').strip()
        email=os.getenv('SEED_ADMIN_EMAIL','').strip().lower()
        password=os.getenv('SEED_ADMIN_PASSWORD','')
        if username or email or password:
            if not all((username,email,password)):
                raise ValueError('Phải có đủ 3 biến SEED_ADMIN_USERNAME, SEED_ADMIN_EMAIL, SEED_ADMIN_PASSWORD')
            checker=RegisterService(db)
            checker.check_username(username)
            checker.check_email(email)
            checker.check_password(password)
            existing=db.scalar(select(User).where((User.username==username)|(User.email==email)))
            if existing is None:
                db.add(User(username=username,email=email,hashPassword=checker.hash_password(password),role='ADMIN'))
                db.commit()
                print('Đã tạo ADMIN từ biến môi trường (không in mật khẩu).')
            elif existing.role!='ADMIN' or existing.username!=username or existing.email!=email:
                raise ValueError('Tên đăng nhập/email trùng người dùng khác; không tự nâng quyền')
            else:print('ADMIN đã tồn tại; không thay đổi mật khẩu.')
        print(f'Hoàn tất seed: {created} thuật toán mới. Không xóa dữ liệu cũ.')

if __name__=='__main__':seed()
```

FE/eslint.config.js
```
import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'
import { globalIgnores } from 'eslint/config'

export default tseslint.config([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      reactHooks.configs['recommended-latest'],
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
    },
  },
])
```

FE/index.html
```
<!doctype html>
<html lang="vi">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <meta name="description" content="Trực quan hóa, tìm hiểu và làm chủ thuật toán qua từng bước mô phỏng." />
    <meta name="theme-color" content="#0b1020" />
    <title>AlgoVisual – Hệ thống mô phỏng thuật toán</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

FE/package.json
```
{
  "name": "algo-web-fe",
  "private": true,
  "version": "0.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "lint": "eslint .",
    "preview": "vite preview"
  },
  "dependencies": {
    "bootstrap": "^5.3.8",
    "react": "^19.1.1",
    "react-bootstrap": "^2.10.10",
    "react-dom": "^19.1.1"
  },
  "devDependencies": {
    "@eslint/js": "^9.33.0",
    "@types/react": "^19.1.10",
    "@types/react-dom": "^19.1.7",
    "@vitejs/plugin-react": "^5.0.0",
    "eslint": "^9.33.0",
    "eslint-plugin-react-hooks": "^5.2.0",
    "eslint-plugin-react-refresh": "^0.4.20",
    "globals": "^16.3.0",
    "typescript": "~5.8.3",
    "typescript-eslint": "^8.39.1",
    "vite": "^7.1.2"
  }
}
```

FE/tsconfig.app.json
```
{
  "compilerOptions": {
    "tsBuildInfoFile": "./node_modules/.tmp/tsconfig.app.tsbuildinfo",
    "target": "ES2022",
    "useDefineForClassFields": true,
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,

    /* Bundler mode */
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "verbatimModuleSyntax": true,
    "moduleDetection": "force",
    "noEmit": true,
    "jsx": "react-jsx",

    /* Linting */
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "erasableSyntaxOnly": true,
    "noFallthroughCasesInSwitch": true,
    "noUncheckedSideEffectImports": true
  },
  "include": ["src"]
}
```

FE/tsconfig.json
```
{
  "files": [],
  "references": [
    { "path": "./tsconfig.app.json" },
    { "path": "./tsconfig.node.json" }
  ]
}
```

FE/tsconfig.node.json
```
{
  "compilerOptions": {
    "tsBuildInfoFile": "./node_modules/.tmp/tsconfig.node.tsbuildinfo",
    "target": "ES2023",
    "lib": ["ES2023"],
    "module": "ESNext",
    "skipLibCheck": true,

    /* Bundler mode */
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "verbatimModuleSyntax": true,
    "moduleDetection": "force",
    "noEmit": true,

    /* Linting */
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "erasableSyntaxOnly": true,
    "noFallthroughCasesInSwitch": true,
    "noUncheckedSideEffectImports": true
  },
  "include": ["vite.config.ts"]
}
```

FE/vite.config.ts
```
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
```

BE/alembic/script.py.mako
```
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}
"""
from alembic import op
import sqlalchemy as sa
${imports if imports else ""}
revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}

def upgrade():
    ${upgrades if upgrades else "pass"}

def downgrade():
    ${downgrades if downgrades else "pass"}
```

BE/Models/Algorithms.py
```
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
```

BE/Models/Base.py
```
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
```

BE/Models/Interaction.py
```
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
```

BE/Models/Users.py
```
from datetime import datetime, timezone

from sqlalchemy import DateTime, String, text
from sqlalchemy.orm import Mapped, mapped_column

from Models.Base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    hashPassword: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    role: Mapped[str] = mapped_column(
        String(10), nullable=False, default="USER", server_default=text("'USER'")
    )
    fullName: Mapped[str | None] = mapped_column(String(100), nullable=True)
    avatarUrl: Mapped[str | None] = mapped_column(String(500), nullable=True)
    createdAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc), server_default=text("CURRENT_TIMESTAMP")
    )
```

BE/Controllers/AlgorithmsController.py
```
from typing import Literal
from fastapi import APIRouter,Depends,Query,Response
from sqlalchemy.orm import Session
from database import get_db
from Models.Users import User
from Schemas.ContentSchemas import AlgorithmInput,CategoryInput,BannerInput,ProgressInput
from Services.AuthDependencies import get_current_user,require_admin
from Services.AlgorithmService import AlgorithmService
from Services.InteractionService import InteractionService
from Schemas.ResponseSchemas import (AlgorithmPage, AlgorithmSummary, AlgorithmDetail, CategoryResponse, BannerResponse, HomeResponse, ProgressResponse, MessageResponse)

router=APIRouter(tags=['Thuật toán và danh mục'])

@router.get('/categories', response_model=list[CategoryResponse])
def get_categories(user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    return AlgorithmService(db).get_categories()

@router.post('/categories',status_code=201,response_model=CategoryResponse)
def create_category(data:CategoryInput,admin:User=Depends(require_admin),db:Session=Depends(get_db)):
    return AlgorithmService(db).create_category(data)

@router.put('/categories/{category_id}', response_model=CategoryResponse)
def update_category(category_id:int,data:CategoryInput,admin:User=Depends(require_admin),db:Session=Depends(get_db)):
    return AlgorithmService(db).update_category(category_id,data)

@router.delete('/categories/{category_id}',status_code=204)
def delete_category(category_id:int,admin:User=Depends(require_admin),db:Session=Depends(get_db)):
    AlgorithmService(db).delete_category(category_id)
    return Response(status_code=204)

@router.get('/algorithms', response_model=AlgorithmPage)
def list_algorithms(page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100),
                    category_id:int|None=None,difficulty:Literal['EASY','MEDIUM','HARD']|None=None,
                    sort:Literal['name','newest','rating']='name',
                    user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    return AlgorithmService(db).list_algorithms(page,page_size,category_id,difficulty,sort)

@router.post('/algorithms',status_code=201,response_model=AlgorithmDetail)
def create_algorithm(data:AlgorithmInput,admin:User=Depends(require_admin),db:Session=Depends(get_db)):
    return AlgorithmService(db).save_algorithm(data)

@router.get('/algorithms/{slug_or_id}',response_model=AlgorithmDetail)
def get_algorithm(slug_or_id:str,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    return AlgorithmService(db).get_algorithm(slug_or_id)

@router.put('/algorithms/{algorithm_id}',response_model=AlgorithmDetail)
def update_algorithm(algorithm_id:int,data:AlgorithmInput,admin:User=Depends(require_admin),db:Session=Depends(get_db)):
    service=AlgorithmService(db)
    return service.save_algorithm(data,service.require_algorithm(algorithm_id))

@router.delete('/algorithms/{algorithm_id}',status_code=204)
def delete_algorithm(algorithm_id:int,admin:User=Depends(require_admin),db:Session=Depends(get_db)):
    AlgorithmService(db).soft_delete(algorithm_id)
    return Response(status_code=204)

@router.get('/algorithms/{algorithm_id}/progress',response_model=ProgressResponse)
def get_progress(algorithm_id:int,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    return InteractionService(db).get_progress(algorithm_id,user.id)

@router.put('/algorithms/{algorithm_id}/progress',response_model=ProgressResponse)
def set_progress(algorithm_id:int,data:ProgressInput,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    return InteractionService(db).set_progress(algorithm_id,user.id,data)

@router.post('/algorithms/{algorithm_id}/favorite',response_model=MessageResponse)
def save_favorite(algorithm_id:int,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    return InteractionService(db).set_favorite(algorithm_id,user.id)

@router.delete('/algorithms/{algorithm_id}/favorite',status_code=204)
def remove_favorite(algorithm_id:int,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    InteractionService(db).delete_favorite(algorithm_id,user.id)
    return Response(status_code=204)

@router.get('/home',response_model=HomeResponse)
def home(user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    from sqlalchemy import func,select
    from Models.Algorithms import Algorithm
    from Models.Users import User as UserModel
    from Services.HomeCache import get_or_build
    def build():
        svc=AlgorithmService(db)
        featured=svc.list_algorithms(1,6,None,None,'rating')['data']
        return {'intro':{'title':'Học thuật toán qua lý thuyết và mô phỏng',
                         'description':'Khám phá cấu trúc dữ liệu và thuật toán bằng tiếng Việt.'},
                'banners':svc.banners(),'featured_algorithms':featured,'categories':svc.get_categories(),
                'stats':{'algorithms':db.scalar(select(func.count(Algorithm.id)).where(Algorithm.is_deleted.is_(False))) or 0,
                         'users':db.scalar(select(func.count(UserModel.id))) or 0}}
    return get_or_build(build)

@router.get('/home/banners',response_model=list[BannerResponse])
def banners(user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    return AlgorithmService(db).banners()

@router.post('/home/banners',status_code=201,response_model=BannerResponse)
def create_banner(data:BannerInput,admin:User=Depends(require_admin),db:Session=Depends(get_db)):
    return AlgorithmService(db).create_banner(data)

@router.put('/home/banners/{id}',response_model=BannerResponse)
def update_banner(id:int,data:BannerInput,admin:User=Depends(require_admin),db:Session=Depends(get_db)):
    return AlgorithmService(db).change_banner(id,data)

@router.delete('/home/banners/{id}',status_code=204)
def delete_banner(id:int,admin:User=Depends(require_admin),db:Session=Depends(get_db)):
    AlgorithmService(db).delete_banner(id)
    return Response(status_code=204)
```

BE/Controllers/AuthController.py
```
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from database import get_db
from Models.Users import User
from Schemas.ChangePasswordRequest import ChangePasswordRequest
from Schemas.ForgotPasswordRequest import ForgotPasswordRequest
from Schemas.LoginRequest import LoginRequest
from Schemas.LogoutRequest import LogoutRequest
from Schemas.RefreshRequest import RefreshRequest
from Schemas.RegisterRequest import RegisterRequest
from Schemas.ResetPasswordRequest import ResetPasswordRequest
from Services.AuthDependencies import get_current_user
from Services.AuthError import AuthError
from Services.Login import LoginService
from Services.MailService import MailService
from Services.PasswordService import PasswordService
from Services.RateLimiter import auth_rate_limiter
from Services.Register import RegisterService, RegistrationError
from Services.SessionService import SessionService
from Schemas.ResponseSchemas import RegisterResponse, LoginResponse, TokenResponse, MessageResponse


class AuthController:
    def __init__(self):
        self.router = APIRouter(prefix="/auth", tags=["Authentication"])
        self.router.add_api_route("/register", self.register, methods=["POST"], status_code=201, response_model=RegisterResponse)
        self.router.add_api_route("/login", self.login, methods=["POST"], response_model=LoginResponse)
        self.router.add_api_route("/refresh", self.refresh, methods=["POST"], response_model=TokenResponse)
        self.router.add_api_route("/logout", self.logout, methods=["POST"], response_model=MessageResponse)
        self.router.add_api_route("/forgot-password", self.forgot_password, methods=["POST"], response_model=MessageResponse)
        self.router.add_api_route("/reset-password", self.reset_password, methods=["POST"], response_model=MessageResponse)
        self.router.add_api_route("/change-password", self.change_password, methods=["POST"], response_model=MessageResponse)

    @staticmethod
    def _raise_http(exc: AuthError | RegistrationError) -> None:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    @staticmethod
    def _check_limit(key: str, limit: int, window_seconds: int) -> None:
        try:
            auth_rate_limiter.check(key, limit, window_seconds)
        except AuthError as exc:
            raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    @staticmethod
    def _client_key(request: Request, action: str) -> str:
        # Do not trust X-Forwarded-For without a configured trusted reverse proxy.
        return f"{action}:{request.client.host if request.client else 'unknown'}"

    def register(self, data: RegisterRequest, request: Request,
                 background_tasks: BackgroundTasks, session: Session = Depends(get_db)):
        self._check_limit(self._client_key(request, "register"), 10, 600)
        try:
            user = RegisterService(session).register_user(
                data.username, data.password, data.email
            )
        except RegistrationError as exc:
            self._raise_http(exc)
        background_tasks.add_task(MailService().welcome, user.email, user.username)
        return {"id": user.id, "username": user.username, "email": user.email, "role": user.role}

    def login(self, data: LoginRequest, request: Request,
              session: Session = Depends(get_db)):
        key = f"{self._client_key(request, 'login')}:{data.login.strip().lower()}"
        self._check_limit(self._client_key(request, "login-ip"), 100, 900)
        self._check_limit(key, 5, 900)
        user = LoginService(session).login_user(data.login, data.password)
        if user is None:
            raise HTTPException(401, detail="Tên đăng nhập/email hoặc mật khẩu không đúng")
        auth_rate_limiter.clear(key)
        tokens = SessionService(session).issue(user, data.remember_me)
        return {
            "message": "Đăng nhập thành công", **tokens,
            "user": {"id": user.id, "username": user.username, "email": user.email, "role": user.role},
        }

    def refresh(self, data: RefreshRequest, request: Request,
                session: Session = Depends(get_db)):
        self._check_limit(self._client_key(request, "refresh"), 50, 60)
        try:
            return SessionService(session).refresh(data.refresh_token)
        except AuthError as exc:
            self._raise_http(exc)

    def logout(self, data: LogoutRequest, request: Request,
               session: Session = Depends(get_db),
               current_user: User = Depends(get_current_user)):
        self._check_limit(self._client_key(request, "logout"), 30, 60)
        try:
            SessionService(session).logout(current_user, data.refresh_token)
        except AuthError as exc:
            self._raise_http(exc)
        return {"message": "Đăng xuất thành công"}

    def forgot_password(self, data: ForgotPasswordRequest, request: Request,
                        background_tasks: BackgroundTasks,
                        session: Session = Depends(get_db)):
        self._check_limit(self._client_key(request, "forgot"), 5, 600)
        result = PasswordService(session).request_reset(data.email)
        if result is not None:
            user, token = result
            background_tasks.add_task(MailService().reset_link, user.email, token)
        return {"message": "Nếu email tồn tại, liên kết đặt lại mật khẩu đã được gửi"}

    def reset_password(self, data: ResetPasswordRequest, request: Request,
                       background_tasks: BackgroundTasks,
                       session: Session = Depends(get_db)):
        self._check_limit(self._client_key(request, "reset"), 10, 600)
        try:
            user = PasswordService(session).reset(
                data.token, data.new_password, data.confirm_password
            )
        except AuthError as exc:
            self._raise_http(exc)
        background_tasks.add_task(MailService().password_changed, user.email)
        return {"message": "Đổi mật khẩu thành công"}

    def change_password(self, data: ChangePasswordRequest, request: Request,
                        background_tasks: BackgroundTasks,
                        session: Session = Depends(get_db),
                        current_user: User = Depends(get_current_user)):
        limit_key = f"{self._client_key(request, 'change')}:{current_user.id}"
        self._check_limit(limit_key, 5, 900)
        try:
            user = PasswordService(session).change(
                current_user, data.current_password, data.new_password,
                data.confirm_password
            )
        except AuthError as exc:
            self._raise_http(exc)
        background_tasks.add_task(MailService().password_changed, user.email)
        return {"message": "Đổi mật khẩu thành công"}
```

BE/Controllers/InteractionsController.py
```
from typing import Literal
from fastapi import APIRouter,Depends,Query,Response,Request,HTTPException
from sqlalchemy.orm import Session
from database import get_db
from Models.Users import User
from Schemas.ContentSchemas import CommentInput,CommentEditInput,RatingInput
from Services.AuthDependencies import get_current_user
from Services.InteractionService import InteractionService
from Services.RateLimiter import auth_rate_limiter
from Services.AuthError import AuthError
from Schemas.ResponseSchemas import CommentResponse,CommentPage,RatingResponse

router=APIRouter(tags=['Bình luận và đánh giá'])

@router.get('/algorithms/{algorithm_id}/comments',response_model=CommentPage)
def comments(algorithm_id:int,page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100),
             sort:Literal['newest','oldest']='newest',user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    return InteractionService(db).list_comments(algorithm_id,user.id,page,page_size,sort)

@router.post('/algorithms/{algorithm_id}/comments',status_code=201,response_model=CommentResponse)
def add_comment(algorithm_id:int,data:CommentInput,request:Request,
                user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    try:auth_rate_limiter.check(f'comment:{user.id}',10,60)
    except AuthError as exc:raise HTTPException(429,str(exc))
    return InteractionService(db).add_comment(algorithm_id,user,data)

@router.get('/comments/{comment_id}/replies',response_model=CommentPage)
def replies(comment_id:int,page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100),
            user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    service=InteractionService(db)
    parent=service._comment(comment_id)
    return service.list_comments(parent.algorithm_id,user.id,page,page_size,'oldest',comment_id)

@router.put('/comments/{comment_id}',response_model=CommentResponse)
def edit_comment(comment_id:int,data:CommentEditInput,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    return InteractionService(db).update_comment(comment_id,user,data)

@router.delete('/comments/{comment_id}',status_code=204)
def delete_comment(comment_id:int,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    InteractionService(db).delete_comment(comment_id,user)
    return Response(status_code=204)

@router.put('/algorithms/{algorithm_id}/rating',response_model=RatingResponse)
def rate(algorithm_id:int,data:RatingInput,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    return InteractionService(db).set_rating(algorithm_id,user.id,data.score)

@router.get('/algorithms/{algorithm_id}/rating',response_model=RatingResponse)
def get_rating(algorithm_id:int,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    return InteractionService(db).stats(algorithm_id,user.id)

@router.delete('/algorithms/{algorithm_id}/rating',status_code=204)
def delete_rating(algorithm_id:int,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    InteractionService(db).delete_rating(algorithm_id,user.id)
    return Response(status_code=204)
```

BE/Controllers/SearchController.py
```
from typing import Literal
from fastapi import APIRouter,Depends,Query
from sqlalchemy.orm import Session
from Models.Users import User
from database import get_db
from Services.AuthDependencies import get_current_user
from Services.SearchService import SearchService
from Schemas.ResponseSchemas import SearchPage,SearchSuggestion

router=APIRouter(prefix='/search',tags=['Tìm kiếm'])

@router.get('',response_model=SearchPage)
def search(q:str=Query(min_length=1,max_length=100),category_id:int|None=None,
           difficulty:Literal['EASY','MEDIUM','HARD']|None=None,
           page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100),
           user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    return SearchService(db).search(q,page,page_size,category_id,difficulty)

@router.get('/suggestions',response_model=list[SearchSuggestion])
def suggest(q:str=Query(min_length=1,max_length=100),limit:int=Query(5,ge=1,le=20),
            user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    return SearchService(db).suggest(q,limit)
```

BE/Controllers/UsersController.py
```
from fastapi import APIRouter,Depends,Query
from sqlalchemy.orm import Session
from database import get_db
from Models.Users import User
from Schemas.ContentSchemas import ProfileInput,RoleInput
from Services.AuthDependencies import get_current_user,require_admin
from Services.ContentHelpers import user_out
from Services.InteractionService import InteractionService
from Services.UserService import UserService
from Schemas.ResponseSchemas import UserResponse, UserPage, FavoritePage

router=APIRouter(prefix='/users',tags=['Người dùng'])

@router.get('/me', response_model=UserResponse)
def me(user:User=Depends(get_current_user)):
    return user_out(user)

@router.patch('/me', response_model=UserResponse)
def edit_me(data:ProfileInput,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    return UserService(db).update_profile(user,data)

@router.get('/me/favorites', response_model=FavoritePage)
def my_favorites(page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100),
                user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    return InteractionService(db).favorites(user.id,page,page_size)

@router.get('', response_model=UserPage)
def users(page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100),
          q:str|None=None,role:str|None=Query(None,pattern='^(USER|ADMIN)$'),
          admin:User=Depends(require_admin),db:Session=Depends(get_db)):
    return UserService(db).list_users(page,page_size,q,role)

@router.patch('/{user_id}/role', response_model=UserResponse)
def update_role(user_id:int,data:RoleInput,admin:User=Depends(require_admin),db:Session=Depends(get_db)):
    return UserService(db).change_role(admin,user_id,data.role)
```

BE/Repositories/AlgorithmRepository.py
```
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
```

BE/Repositories/AuthRepository.py
```
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from Models.Users import User


class AuthRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_user_by_id(self, user_id: int) -> User | None:
        return self.session.get(User, user_id)

    def get_user_by_username(self, username: str) -> User | None:
        return self.session.scalar(select(User).where(User.username == username))

    def get_user_by_email(self, email: str) -> User | None:
        return self.session.scalar(
            select(User).where(func.lower(User.email) == email.strip().lower())
        )

    def get_user_by_username_or_email(self, login: str) -> User | None:
        if "@" in login:
            return self.get_user_by_email(login)
        return self.get_user_by_username(login)

    def add_user(self, username: str, hashPassword: str, email: str) -> User | None:
        user = User(username=username, hashPassword=hashPassword, email=email, role="USER")
        self.session.add(user)
        try:
            self.session.flush()
            self.session.refresh(user)
            return user
        except IntegrityError:
            self.session.rollback()
            return None
```

BE/Repositories/InteractionRepository.py
```
from sqlalchemy import func, select
from sqlalchemy.orm import Session
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
```

BE/Repositories/UserRepository.py
```
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
```

BE/Schemas/ContentSchemas.py
```
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
```

BE/Schemas/LoginRequest.py
```
from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    login: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1)
    remember_me: bool = False
```

BE/Schemas/LogoutRequest.py
```
from pydantic import BaseModel, Field


class LogoutRequest(BaseModel):
    refresh_token: str = Field(min_length=1)
```

BE/Schemas/RefreshRequest.py
```
from pydantic import BaseModel, Field


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)
```

BE/Schemas/RegisterRequest.py
```
from pydantic import BaseModel


class RegisterRequest(BaseModel):
    username: str
    password: str
    email: str
```

BE/Schemas/ResponseSchemas.py
```
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
```

BE/scripts/check_release.py
```
"""Non-destructive pre-release audit; never prints secrets.

From BE: py scripts/check_release.py [--production]
"""
import argparse
import os
from pathlib import Path
import sys

from dotenv import load_dotenv

ROOT=Path(__file__).resolve().parents[1]
load_dotenv(ROOT/'.env')


def audit(production=False):
    errors=[]
    warnings=[]
    notes=[]
    get=lambda name:os.getenv(name,'').strip()
    secret=get('JWT_SECRET_KEY')
    if not secret or len(secret)<32 or any(x in secret.upper() for x in ('REPLACE', 'SECRET_RIENG', 'PASSWORD', 'CHANGE_ME')):
        errors.append('JWT_SECRET_KEY: cần khóa ngẫu nhiên riêng, dài ít nhất 32 ký tự.')
    if get('JWT_ALGORITHM') and get('JWT_ALGORITHM')!='HS256':
        errors.append('JWT_ALGORITHM: dự án chỉ hỗ trợ HS256.')
    if not get('DATABASE_URL'):
        errors.append('Thiếu DATABASE_URL trong .env.')
    if not (ROOT/'alembic.ini').exists():
        errors.append('Không tìm thấy alembic.ini.')
    if not (ROOT/'tests'/'test_auth.py').exists():
        errors.append('Không tìm thấy bộ test Auth.')
    if get('SQLALCHEMY_ECHO').lower() in ('true','yes','1'):
        warnings.append('SQLALCHEMY_ECHO đang bật, có thể log thông tin SQL.')

    smtp_fields=['SMTP_HOST','SMTP_FROM','SMTP_USERNAME','SMTP_PASSWORD']
    smtp_on=all(get(s) for s in smtp_fields)
    if not smtp_on:
        warnings.append('SMTP chưa đầy đủ; chưa gửi email thật được.')
    if not get('FRONTEND_RESET_PASSWORD_URL'):
        warnings.append('Thiếu FRONTEND_RESET_PASSWORD_URL; email reset sẽ không được gửi.')
    if get('SMTP_HOST').lower()=='sandbox.smtp.mailtrap.io':
        warnings.append('Mailtrap Sandbox chỉ giữ thư thử nghiệm, KHÔNG chuyển thư đến inbox người dùng.')

    if production:
        if not get('REDIS_URL'):
            errors.append('Thiếu REDIS_URL cho cache/rate limit nhiều worker.')
        if not get('TRUSTED_HOSTS'):
            errors.append('Thiếu TRUSTED_HOSTS cho reverse proxy/host whitelist.')
        if not get('CORS_ORIGINS') or '*' in get('CORS_ORIGINS'):
            errors.append('CORS_ORIGINS phải cấu hình origin FE thật, không được wildcard.')
        if get('SMTP_HOST')=='sandbox.smtp.mailtrap.io' or not smtp_on:
            errors.append('Production phải dùng SMTP gửi thư thật, không dùng Mailtrap Sandbox.')
        if not get('FRONTEND_RESET_PASSWORD_URL').startswith('https://'):
            errors.append('FRONTEND_RESET_PASSWORD_URL phải là HTTPS khi deploy.')
        if get('DATABASE_URL').lower().startswith('sqlite:'):
            warnings.append('SQLite có thể hạn chế write concurrency ở production; cân nhắc PostgreSQL.')
        if get('FORCE_HTTPS').lower() not in ('true','1'):
            warnings.append('Hãy bắt buộc HTTPS tại reverse proxy (hoặc FORCE_HTTPS=true nếu proxy đúng).')
    else:
        notes.append('Đây là rà soát cấu hình local, KHÔNG xác nhận hệ thống chạy production an toàn.')

    for prefix,arr in [('LỖI',errors),('CẦN XỬ LÝ',warnings),('GHI CHÚ',notes)]:
        for line in arr:
            print(f'[{prefix}] {line}')
    print(f'Tổng kết: {len(errors)} lỗi bắt buộc, {len(warnings)} cảnh báo.')
    return 1 if errors else 0


if __name__=='__main__':
    parser=argparse.ArgumentParser(description='Kiểm tra cấu hình phát hành BE Algo_web')
    parser.add_argument('--production',action='store_true',help='Chặn phát hành nếu thiếu cấu hình production')
    args=parser.parse_args()
    sys.exit(audit(args.production))
```

BE/scripts/load_test.js
```
// Algo_web — k6 load test. Use only against a local/test server you own.
// Run: k6 run -e BASE_URL=http://127.0.0.1:8000 -e ACCESS_TOKEN=<token> scripts/load_test.js
// Do not commit a real access token or write it into the source file.
import http from 'k6/http';
import { check, sleep } from 'k6';

const base = (__ENV.BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');
const token = __ENV.ACCESS_TOKEN || '';
if (!token) {
  throw new Error('Thiếu ACCESS_TOKEN. Đăng nhập qua Swagger và truyền bằng -e ACCESS_TOKEN=...');
}

export const options = {
  stages: [
    { duration: '20s', target: 5 },
    { duration: '40s', target: 10 },
    { duration: '10s', target: 0 },
  ],
  thresholds: {
    http_req_duration: ['p(95)<3000'], // TODO: mục tiêu phần lớn request dưới 3s
    http_req_failed: ['rate<0.01'],
  },
};

const paths = [
  '/home',
  '/categories',
  '/algorithms?page=1&page_size=20',
  '/search?q=bubble&page=1&page_size=20',
];

export default function () {
  const path = paths[__ITER % paths.length];
  const res = http.get(base + path, {
    headers: { Authorization: `Bearer ${token}` },
    tags: { endpoint: path.split('?')[0] },
    timeout: '10s',
  });
  check(res, { 'HTTP 200': (r) => r.status === 200 });
  sleep(1);
}
```

BE/Services/AlgorithmService.py
```
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
```

BE/Services/AuthDependencies.py
```
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from database import get_db
from Models.Users import User
from Repositories.AuthRepository import AuthRepository
from Services.JWTService import JWTService

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: Session = Depends(get_db),
) -> User:
    unauthorized = HTTPException(
        status_code=401,
        detail="Phiên đăng nhập không hợp lệ hoặc đã hết hạn",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise unauthorized
    payload = JWTService().decode_access_token(credentials.credentials)
    if payload is None:
        raise unauthorized
    user = AuthRepository(session).get_user_by_id(int(payload["sub"]))
    if user is None:
        raise unauthorized
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Bạn không có quyền quản trị")
    return user
```

BE/Services/AuthError.py
```
class AuthError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code
```

BE/Services/ContentHelpers.py
```
"""Serialize persisted objects without exposing internal SQLAlchemy state."""
import re
import unicodedata
from Models.Algorithms import Algorithm, Category, HomeBanner
from Models.Users import User
from Repositories.InteractionRepository import InteractionRepository


def normalized(value:str) -> str:
    value=unicodedata.normalize('NFD',value.replace('đ','d').replace('Đ','D'))
    return re.sub(r'\s+',' ',''.join(c for c in value if not unicodedata.combining(c)).lower()).strip()


def slugify(value):
    return re.sub(r'-+','-',re.sub(r'[^a-z0-9]+','-',normalized(value))).strip('-')


def user_out(user:User):
    return {'id':user.id,'username':user.username,'email':user.email,'full_name':user.fullName,'avatar_url':user.avatarUrl,'role':user.role,'created_at':user.createdAt}


def category_out(category:Category,count:int|None=None):
    data={'id':category.id,'name':category.name,'slug':category.slug,'description':category.description}
    if count is not None:data['algorithm_count']=count
    return data


def banner_out(b:HomeBanner):
    return {k:getattr(b,k) for k in ('id','title','image_url','link_url','sort_order','is_active')}


def algorithm_out(a:Algorithm,interactions:InteractionRepository,detailed=False,rating=None):
    avg,count=rating if rating is not None else interactions.rating_stats(a.id)
    data={'id':a.id,'slug':a.slug,'name':a.name,'summary':a.summary,'category':a.category.name,
          'category_id':a.category_id,'difficulty':a.difficulty,'avg_rating':avg,'rating_count':count,
          'has_simulation':a.has_simulation}
    if detailed:
        data.update({
          'theory':a.theory,'pseudocode':a.pseudocode,
          'code_samples':[{'id':c.id,'language':c.language,'code':c.code} for c in a.code_samples],
          'complexity':{'time_best':a.time_best,'time_average':a.time_average,'time_worst':a.time_worst,'space':a.space_complexity},
          'tags':[{'id':t.id,'name':t.name,'slug':t.slug} for t in a.tags],
          'examples':[{'id':e.id,'title':e.title,'input_data':e.input_data,'expected_output':e.expected_output,'explanation':e.explanation,'sort_order':e.sort_order} for e in sorted(a.examples,key=lambda x:x.sort_order)],
          'diagrams':[{'id':d.id,'title':d.title,'diagram_type':d.diagram_type,'source_text':d.source_text,'image_url':d.image_url,'sort_order':d.sort_order} for d in sorted(a.diagrams,key=lambda x:x.sort_order)],
          'visualization_config':None if a.visualization_config is None else {'renderer_key':a.visualization_config.renderer_key,'config_json':a.visualization_config.config_json},
          'comment_count':interactions.comment_count(a.id),
          'created_at':a.created_at,'updated_at':a.updated_at,
        })
    return data


def comment_out(c,repo:InteractionRepository,current_id:int,reply_count=None):
    return {'id':c.id,'content':c.content,
       'author':{'id':c.author.id,'username':c.author.username,'avatar_url':c.author.avatarUrl},
       'algorithm_id':c.algorithm_id,'parent_id':c.parent_id, 'reply_count':repo.reply_count(c.id) if reply_count is None else reply_count,
       'created_at':c.created_at,'updated_at':c.updated_at,'is_mine':c.user_id==current_id}
```

BE/Services/HomeCache.py
```
"""TTL cache for public catalog data only.

Local: bounded cache for development. With REDIS_URL: shared cache and invalidation
across workers. Never cache user-specific responses (e.g., /users/me).
"""
import json
import os
from collections import OrderedDict
from threading import RLock
from time import monotonic

from fastapi.encoders import jsonable_encoder
from Services.RedisClient import redis_client

_lock = RLock()
_cache: OrderedDict[str, tuple[float, object]] = OrderedDict()
_MAX_ENTRIES = 256


def get_or_build(builder, ttl_seconds=300, key='home'):
    client = redis_client()
    if client is not None:
        try:
            version = client.get('algoweb:cache:epoch') or b'0'
            if isinstance(version, bytes):
                version = version.decode('ascii')
            cache_key = f'algoweb:cache:{version}:{key}'
            cached = client.get(cache_key)
            if cached is not None:
                return json.loads(cached)
            data = jsonable_encoder(builder())
            client.set(cache_key, json.dumps(data, ensure_ascii=False), ex=int(ttl_seconds))
            return data
        except Exception as exc:
            raise RuntimeError('Redis cache không khả dụng; vui lòng kiểm tra REDIS_URL') from exc

    with _lock:
        now = monotonic()
        found = _cache.get(key)
        if found is not None and found[0] > now:
            _cache.move_to_end(key)
            return found[1]
        if found is not None:
            _cache.pop(key, None)
        data = builder()
        _cache[key] = (monotonic() + ttl_seconds, data)
        _cache.move_to_end(key)
        while len(_cache) > _MAX_ENTRIES:
            _cache.popitem(last=False)
        return data


def invalidate():
    client = redis_client()
    if client is not None:
        try:
            client.incr('algoweb:cache:epoch')
        except Exception as exc:
            raise RuntimeError('Không thể làm mới cache Redis') from exc
    with _lock:
        _cache.clear()
```

BE/Services/InteractionService.py
```
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
```

BE/Services/JWTService.py
```
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
from dotenv import load_dotenv
from jwt.exceptions import InvalidTokenError


class JWTService:
    def __init__(self):
        load_dotenv(Path(__file__).resolve().parents[1] / ".env")
        self.secret_key = os.getenv("JWT_SECRET_KEY")
        self.algorithm = os.getenv("JWT_ALGORITHM", "HS256")
        self.expire_minutes = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
        if not self.secret_key:
            raise ValueError("Thiếu JWT_SECRET_KEY trong BE/.env")
        if self.algorithm != "HS256":
            raise ValueError("Chỉ hỗ trợ JWT_ALGORITHM=HS256")
        if self.expire_minutes < 1:
            raise ValueError("ACCESS_TOKEN_EXPIRE_MINUTES phải >= 1")

    @property
    def expires_in(self) -> int:
        return self.expire_minutes * 60

    def create_access_token(self, user_id: int, username: str, role: str = "USER") -> str:
        now = datetime.now(timezone.utc)
        payload = {
            "sub": str(user_id),
            "username": username,
            "role": role,
            "token_type": "access",
            "iat": now,
            "exp": now + timedelta(minutes=self.expire_minutes),
        }
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def decode_access_token(self, token: str) -> dict | None:
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm],
                options={"require": ["sub", "iat", "exp", "token_type"]},
            )
            if payload.get("token_type") != "access":
                return None
            if not str(payload.get("sub", "")).isdigit():
                return None
            return payload
        except (InvalidTokenError, ValueError, TypeError):
            return None
```

BE/Services/Login.py
```
from pwdlib import PasswordHash
from sqlalchemy.orm import Session

from Repositories.AuthRepository import AuthRepository


class LoginService:
    def __init__(self, session: Session):
        self.auth_repository = AuthRepository(session)
        self.password_hash = PasswordHash.recommended()

    def verify_password(self, password, hashed_password):
        return self.password_hash.verify(password, hashed_password)

    def login_user(self, login, password):
        login = login.strip()
        if not login or not password:
            return None

        user = self.auth_repository.get_user_by_username_or_email(login)
        if user is None:
            return None

        if not self.verify_password(password, user.hashPassword):
            return None

        return user
```

BE/Services/MailService.py
```
"""Optional SMTP delivery. No secrets or token values are logged."""
import logging
import os
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path
import smtplib
import ssl
from time import sleep
from urllib.parse import quote

from dotenv import load_dotenv

logger = logging.getLogger(__name__)


class MailService:
    def __init__(self):
        load_dotenv(Path(__file__).resolve().parents[1] / ".env")
        self.host = os.getenv("SMTP_HOST", "")
        self.port = int(os.getenv("SMTP_PORT", "587"))
        self.sender = os.getenv("SMTP_FROM", "")
        self.username = os.getenv("SMTP_USERNAME", "")
        self.password = os.getenv("SMTP_PASSWORD", "")
        self.ssl_enabled = os.getenv("SMTP_SSL", "false").lower() == "true"

    @property
    def enabled(self) -> bool:
        return bool(self.host and self.sender)

    def send(self, to_email: str, subject: str, body: str) -> None:
        if not self.enabled:
            logger.warning("SMTP chưa cấu hình: email không được gửi")
            return
        msg = EmailMessage()
        msg["From"] = self.sender
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.set_content(body)
        for attempt in range(2):
            try:
                if self.ssl_enabled:
                    with smtplib.SMTP_SSL(self.host, self.port, timeout=8,
                                          context=ssl.create_default_context()) as smtp:
                        self._deliver(smtp, msg)
                else:
                    with smtplib.SMTP(self.host, self.port, timeout=8) as smtp:
                        smtp.starttls(context=ssl.create_default_context())
                        self._deliver(smtp, msg)
                return
            except (OSError, smtplib.SMTPException):
                logger.exception("Không gửi được email thông báo")
                if attempt == 0:
                    sleep(1)

    def _deliver(self, smtp, message) -> None:
        if self.username:
            smtp.login(self.username, self.password)
        smtp.send_message(message)

    def welcome(self, email: str, username: str) -> None:
        self.send(email, "Chào mừng bạn đến với Algo_web",
                  f"Xin chào {username},\nTài khoản Algo_web đã được tạo thành công.\n")

    def reset_link(self, email: str, raw_token: str) -> None:
        base_url = os.getenv("FRONTEND_RESET_PASSWORD_URL", "").strip()
        if not base_url:
            logger.warning("Chưa có FRONTEND_RESET_PASSWORD_URL: không thể gửi liên kết")
            return
        separator = "&" if "?" in base_url else "?"
        link = f"{base_url}{separator}token={quote(raw_token, safe='')}"
        self.send(email, "Đặt lại mật khẩu Algo_web",
                  f"Bạn đã yêu cầu đặt lại mật khẩu. Liên kết chỉ dùng một lần, hết hạn sau 20 phút:\n{link}\n\nNếu không yêu cầu, hãy bỏ qua email này.\n")

    def password_changed(self, email: str) -> None:
        now = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
        self.send(email, "Mật khẩu Algo_web đã thay đổi",
                  f"Mật khẩu tài khoản của bạn vừa được thay đổi lúc {now}. Nếu không phải bạn, hãy liên hệ quản trị viên.\n")
```

BE/Services/RateLimiter.py
```
"""Auth and comment rate limits.

Single worker: sliding window in RAM. REDIS_URL: atomic Redis fixed window shared
across processes (recommended for deployment). Do not trust X-Forwarded-For
from untrusted clients; AuthController uses request.client.host.
"""
from collections import defaultdict, deque
from hashlib import sha256
from threading import Lock
from time import monotonic

from Services.AuthError import AuthError
from Services.RedisClient import redis_client

_RATE_SCRIPT = """
local count=redis.call('INCR',KEYS[1])
if count==1 then redis.call('EXPIRE',KEYS[1],ARGV[1]) end
return count
"""


class RateLimiter:
    def __init__(self):
        self._events = defaultdict(deque)
        self._lock = Lock()

    def check(self, key: str, limit: int, window_seconds: int) -> None:
        client = redis_client()
        if client is not None:
            hashed = sha256(key.encode('utf-8')).hexdigest()
            try:
                count = client.eval(_RATE_SCRIPT, 1, f'algoweb:rl:{hashed}', window_seconds)
            except Exception as exc:
                raise AuthError('Hệ thống giới hạn truy cập đang gián đoạn, vui lòng thử lại sau', 503) from exc
            if count > limit:
                raise AuthError('Bạn thao tác quá nhiều lần. Vui lòng thử lại sau.', 429)
            return
        now = monotonic()
        with self._lock:
            events = self._events[key]
            while events and now - events[0] >= window_seconds:
                events.popleft()
            if len(events) >= limit:
                raise AuthError('Bạn thao tác quá nhiều lần. Vui lòng thử lại sau.', 429)
            events.append(now)
            # Bound memory on long-running development servers.
            if len(self._events) > 10000:
                stale = [k for k, v in self._events.items() if not v or now - v[-1] >= window_seconds]
                for k in stale:
                    self._events.pop(k, None)

    def clear(self, key: str) -> None:
        client = redis_client()
        if client is not None:
            try:
                client.delete('algoweb:rl:' + sha256(key.encode('utf-8')).hexdigest())
            except Exception as exc:
                raise AuthError('Không thể cập nhật giới hạn truy cập', 503) from exc
            return
        with self._lock:
            self._events.pop(key, None)


auth_rate_limiter = RateLimiter()
```

BE/Services/RedisClient.py
```
"""Optional shared Redis backend; imported lazily to keep local SQLite setup simple."""
import os
from functools import lru_cache


@lru_cache(maxsize=4)
def _connect(url: str):
    try:
        import redis
    except ImportError as exc:
        raise RuntimeError('Đã cấu hình REDIS_URL nhưng thiếu thư viện redis; cài requirements-production.txt') from exc
    return redis.Redis.from_url(url, socket_connect_timeout=2, socket_timeout=2)


def redis_client():
    url = os.getenv('REDIS_URL', '').strip()
    return _connect(url) if url else None
```

BE/Services/Register.py
```
import re

from pwdlib import PasswordHash
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from Repositories.AuthRepository import AuthRepository


class RegistrationError(Exception):
    """Lỗi nghiệp vụ; Controller chuyển thành HTTP 400 hoặc HTTP 409."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


class RegisterService:
    def __init__(self, session: Session):
        self.session = session
        self.auth_repository = AuthRepository(session)
        self.password_hash = PasswordHash.recommended()

    def check_username(self, username: str) -> bool:
        if not username:
            raise RegistrationError("Tên đăng nhập không được để trống")

        if not 3 <= len(username) <= 50:
            raise RegistrationError("Tên đăng nhập phải có từ 3 đến 50 ký tự")

        if re.fullmatch(r"[A-Za-z0-9_]+", username) is None:
            raise RegistrationError(
                "Tên đăng nhập chỉ được chứa chữ cái không dấu, số và dấu gạch dưới"
            )

        if re.search(r"[A-Za-z]", username) is None:
            raise RegistrationError("Tên đăng nhập phải có ít nhất một chữ cái")

        if re.search(r"[0-9]", username) is None:
            raise RegistrationError("Tên đăng nhập phải có ít nhất một chữ số")

        return True

    def check_password(self, password: str) -> bool:
        if not 8 <= len(password) <= 64:
            raise RegistrationError("Mật khẩu phải có từ 8 đến 64 ký tự")

        if re.search(r"[A-Z]", password) is None:
            raise RegistrationError("Mật khẩu phải có ít nhất một chữ cái in hoa")

        if re.search(r"[0-9]", password) is None:
            raise RegistrationError("Mật khẩu phải có ít nhất một chữ số")

        if re.search(r"[^A-Za-z0-9]", password) is None:
            raise RegistrationError("Mật khẩu phải có ít nhất một ký tự đặc biệt")

        return True

    def check_email(self, email: str) -> bool:
        if not email:
            raise RegistrationError("Email không được để trống")

        if len(email) > 100:
            raise RegistrationError("Email không được vượt quá 100 ký tự")

        email_pattern = r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
        if re.fullmatch(email_pattern, email) is None:
            raise RegistrationError("Định dạng email không hợp lệ")

        return True

    def hash_password(self, password: str) -> str:
        return self.password_hash.hash(password)

    def register_user(self, username: str, password: str, email: str):
        # Username/password giữ nguyên, email chuẩn hóa để tìm kiếm nhất quán.
        email = email.strip().lower()

        self.check_username(username)
        self.check_password(password)
        self.check_email(email)

        if self.auth_repository.get_user_by_username(username) is not None:
            raise RegistrationError("Tên đăng nhập đã tồn tại", status_code=409)

        if self.auth_repository.get_user_by_email(email) is not None:
            raise RegistrationError("Email đã được sử dụng", status_code=409)

        user = self.auth_repository.add_user(
            username,
            self.hash_password(password),
            email,
        )

        if user is None:
            raise RegistrationError(
                "Tên đăng nhập hoặc email đã tồn tại", status_code=409
            )

        try:
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise RegistrationError(
                "Tên đăng nhập hoặc email đã tồn tại", status_code=409
            ) from exc

        return user
```

BE/Services/SearchService.py
```
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
```

BE/Services/SessionService.py
```
"""Issue opaque refresh tokens, rotate on each use, revoke sessions on logout."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import secrets
from uuid import uuid4

from sqlalchemy.orm import Session

from Models.AuthToken import RefreshToken
from Models.Users import User
from Repositories.AuthRepository import AuthRepository
from Repositories.AuthTokenRepository import AuthTokenRepository
from Services.AuthError import AuthError
from Services.JWTService import JWTService


def utc_now() -> datetime:
    # DB fields are UTC-naive for SQLite portability.
    return datetime.now(timezone.utc).replace(tzinfo=None)


def token_hash(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


class SessionService:
    def __init__(self, session: Session):
        self.session = session
        self.repository = AuthTokenRepository(session)
        self.jwt_service = JWTService()

    def _create_refresh(self, user: User, family: str, ttl_days: int) -> str:
        token = secrets.token_urlsafe(48)
        self.repository.save_refresh(RefreshToken(
            user_id=user.id,
            token_hash=token_hash(token),
            family_id=family,
            expires_at=utc_now() + timedelta(days=ttl_days),
        ))
        return token

    def issue(self, user: User, remember_me: bool = False) -> dict:
        family = str(uuid4())
        refresh_token = self._create_refresh(user, family, 30 if remember_me else 7)
        self.session.commit()
        return {
            "access_token": self.jwt_service.create_access_token(user.id, user.username, user.role),
            "refresh_token": refresh_token,
            "expires_in": self.jwt_service.expires_in,
            "token_type": "bearer",
        }

    def refresh(self, raw_token: str) -> dict:
        record = self.repository.find_refresh(token_hash(raw_token))
        now = utc_now()
        if record is None:
            raise AuthError("Refresh token không hợp lệ hoặc đã hết hạn", 401)

        if record.revoked_at is not None:
            # A rotated token replay revokes its entire session family.
            if record.replaced_at is not None:
                self.repository.revoke_family(record.family_id, now)
                self.session.commit()
            raise AuthError("Refresh token không hợp lệ hoặc đã hết hạn", 401)

        if record.expires_at <= now:
            record.revoked_at = now
            self.session.commit()
            raise AuthError("Refresh token không hợp lệ hoặc đã hết hạn", 401)

        user = AuthRepository(self.session).get_user_by_id(record.user_id)
        if user is None:
            raise AuthError("Refresh token không hợp lệ hoặc đã hết hạn", 401)

        record.revoked_at = now
        record.replaced_at = now
        remaining = record.expires_at - now
        ttl_seconds = max(1, int(remaining.total_seconds()))
        new_token = secrets.token_urlsafe(48)
        self.repository.save_refresh(RefreshToken(
            user_id=user.id,
            token_hash=token_hash(new_token),
            family_id=record.family_id,
            expires_at=now + timedelta(seconds=ttl_seconds),
        ))
        self.session.commit()
        return {
            "access_token": self.jwt_service.create_access_token(user.id, user.username, user.role),
            "refresh_token": new_token,
            "expires_in": self.jwt_service.expires_in,
            "token_type": "bearer",
        }

    def logout(self, user: User, raw_token: str) -> None:
        record = self.repository.find_refresh(token_hash(raw_token))
        if record is None or record.user_id != user.id:
            raise AuthError("Refresh token không hợp lệ", 401)
        # Revoke all tokens of the session family (including rotated token).
        self.repository.revoke_family(record.family_id, utc_now())
        self.session.commit()

    def revoke_all(self, user_id: int) -> None:
        self.repository.revoke_user(user_id, utc_now())
```

BE/Services/UserService.py
```
from fastapi import HTTPException
from sqlalchemy.orm import Session
from Models.Users import User
from Repositories.UserRepository import UserRepository
from Services.ContentHelpers import user_out


class UserService:
    def __init__(self,db:Session):
        self.db=db
        self.repo=UserRepository(db)

    def update_profile(self,user:User, data):
        if 'full_name' in data.model_fields_set:
            user.fullName = data.full_name.strip() if data.full_name else None
        if 'avatar_url' in data.model_fields_set:
            user.avatarUrl = data.avatar_url.strip() if data.avatar_url else None
        self.db.commit()
        self.db.refresh(user)
        return user_out(user)

    def list_users(self,page,page_size,q,role):
        users,total=self.repo.search(page,page_size,q,role)
        return {'data':[user_out(x) for x in users], 'meta':{'page':page,'page_size':page_size,'total':total}}

    def change_role(self,current:User, target_id:int, role:str):
        target=self.repo.find(target_id)
        if target is None:raise HTTPException(404,'Không tìm thấy người dùng')
        if target.role=='ADMIN' and role=='USER' and self.repo.number_of_admins()<=1:
            raise HTTPException(409,'Không thể hạ quyền quản trị viên cuối cùng')
        target.role=role
        self.db.commit()
        self.db.refresh(target)
        return user_out(target)
```

BE/tests/conftest.py
```
"""Safeguard: pytest always uses an isolated throwaway SQLite database."""
import os
import sys
import tempfile
from pathlib import Path

import pytest

TEST_DIR=tempfile.TemporaryDirectory(prefix='algoweb-tests-')
os.environ['DATABASE_URL']=f"sqlite:///{Path(TEST_DIR.name, 'test.db').as_posix()}"
os.environ['JWT_SECRET_KEY']='test-only-not-for-deploy-'+'x'*48
os.environ['JWT_ALGORITHM']='HS256'
os.environ['ACCESS_TOKEN_EXPIRE_MINUTES']='30'
# Mask real .env settings, not just remove them: load_dotenv() would otherwise
# repopulate credentials and tests could accidentally deliver real emails.
for key in ('SMTP_HOST','SMTP_USERNAME','SMTP_PASSWORD','SMTP_FROM',
            'FRONTEND_RESET_PASSWORD_URL','REDIS_URL','TRUSTED_HOSTS'):
    os.environ[key]=''
os.environ['FORCE_HTTPS']='false'
os.environ['SQLALCHEMY_ECHO']='false'
os.environ['CORS_ORIGINS']='http://localhost:5173,http://127.0.0.1:5173'
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

@pytest.fixture(scope='session',autouse=True)
def cleanup_sqlite():
    yield
    from database import engine
    engine.dispose()
    TEST_DIR.cleanup()

@pytest.fixture(autouse=True)
def clear_local_rate_limit_between_tests():
    """Avoid in-memory rate-limit state leaking across unrelated test cases."""
    from Services.RateLimiter import auth_rate_limiter
    with auth_rate_limiter._lock:
        auth_rate_limiter._events.clear()
```

BE/tests/test_auth.py
```
"""Run with: py -m pytest BE/tests -q (after installing pytest httpx)."""
from unittest.mock import patch
from fastapi.testclient import TestClient
from main import app
from database import SessionLocal, engine
from Models.Users import User

def test_auth_workflow():
    with TestClient(app) as client:
        register = client.post("/auth/register", json={
            "username": "student123", "password": "Test@1234", "email": "STUDENT@example.com"
        })
        assert register.status_code == 201, register.text
        assert register.json()["role"] == "USER"
        assert register.json()["email"] == "student@example.com"

        assert client.post("/auth/register", json={
            "username": "student124", "password": "Test@1234", "email": "student@example.com"
        }).status_code == 409
        assert client.post("/auth/login", json={
            "login": "student123", "password": "wrong"
        }).status_code == 401

        login = client.post("/auth/login", json={
            "login": "STUDENT@EXAMPLE.COM", "password": "Test@1234", "remember_me": True
        })
        assert login.status_code == 200, login.text
        assert login.json()["access_token"]
        assert login.json()["refresh_token"]
        auth_header = {"Authorization": "Bearer " + login.json()["access_token"]}
        refresh = login.json()["refresh_token"]
        new_tokens = client.post("/auth/refresh", json={"refresh_token": refresh})
        assert new_tokens.status_code == 200, new_tokens.text
        assert new_tokens.json()["refresh_token"] != refresh

        assert client.post("/auth/logout", headers=auth_header, json={
            "refresh_token": new_tokens.json()["refresh_token"]
        }).status_code == 200
        assert client.post("/auth/refresh", json={
            "refresh_token": new_tokens.json()["refresh_token"]
        }).status_code == 401
        assert client.post("/auth/change-password", json={
            "current_password": "Test@1234", "new_password": "New@1234", "confirm_password": "New@1234"
        }).status_code == 401

        new_login = client.post("/auth/login", json={"login": "student123", "password": "Test@1234"})
        token = new_login.json()["access_token"]
        changed = client.post("/auth/change-password", headers={"Authorization": "Bearer " + token}, json={
            "current_password": "Test@1234", "new_password": "New@1234", "confirm_password": "New@1234"
        })
        assert changed.status_code == 200, changed.text
        assert client.post("/auth/login", json={"login": "student123", "password": "Test@1234"}).status_code == 401
        assert client.post("/auth/login", json={"login": "student123", "password": "New@1234"}).status_code == 200

        # Token is delivered by email in production, not returned from API.
        with patch("Services.PasswordService.secrets.token_urlsafe", return_value="test-only-reset-token"):
            assert client.post("/auth/forgot-password", json={"email": "student@example.com"}).status_code == 200
        assert client.post("/auth/forgot-password", json={"email": "unknown@example.com"}).status_code == 200
        reset = client.post("/auth/reset-password", json={
            "token": "test-only-reset-token", "new_password": "Reset@1234", "confirm_password": "Reset@1234"
        })
        assert reset.status_code == 200, reset.text
        assert client.post("/auth/reset-password", json={
            "token": "test-only-reset-token", "new_password": "Again@1234", "confirm_password": "Again@1234"
        }).status_code == 400
        assert client.post("/auth/login", json={"login": "student123", "password": "Reset@1234"}).status_code == 200


def test_errors_and_refresh_replay():
    with TestClient(app) as client:
        assert client.post("/auth/register", content='{"username"abc"}', headers={
            "Content-Type": "application/json"
        }).status_code == 400
        assert client.post("/auth/register", json={
            "username": "bad@name", "password": "Test@1234", "email": "name@example.com"
        }).status_code == 400
        first = client.post("/auth/register", json={
            "username": "replay123", "password": "Test@1234", "email": "replay@example.com"
        })
        assert first.status_code == 201
        login = client.post("/auth/login", json={
            "login": "replay123", "password": "Test@1234"
        })
        old = login.json()["refresh_token"]
        rotated = client.post("/auth/refresh", json={"refresh_token": old})
        assert rotated.status_code == 200
        new = rotated.json()["refresh_token"]
        assert client.post("/auth/refresh", json={"refresh_token": old}).status_code == 401
        # Replaying an old rotated refresh token revokes the whole family.
        assert client.post("/auth/refresh", json={"refresh_token": new}).status_code == 401
        assert client.post("/auth/logout", json={"refresh_token": new}).status_code == 401


def test_rate_limit_wrong_password():
    with TestClient(app) as client:
        register = client.post("/auth/register", json={
            "username": "limited123", "password": "Test@1234", "email": "limited@example.com"
        })
        assert register.status_code == 201
        for _ in range(5):
            assert client.post("/auth/login", json={
                "login": "limited123", "password": "Wrong@1234"
            }).status_code == 401
        assert client.post("/auth/login", json={
            "login": "limited123", "password": "Wrong@1234"
        }).status_code == 429


def test_invalid_bearer_and_admin_permissions():
    from fastapi import Depends
    from Services.AuthDependencies import get_current_user, require_admin
    from Services.JWTService import JWTService

    # Test-only endpoints; they are never added to production main.py.
    if not any(getattr(route, "path", None) == "/_test/protected" for route in app.routes):
        app.add_api_route("/_test/protected", lambda user=Depends(get_current_user): {"id": user.id})
        app.add_api_route("/_test/admin", lambda user=Depends(require_admin): {"id": user.id})
    with TestClient(app) as client:
        r = client.post("/auth/register", json={
            "username": "role123", "password": "Test@1234", "email": "role@example.com"
        })
        assert r.status_code == 201
        assert client.get("/_test/protected").status_code == 401
        assert client.get("/_test/protected", headers={"Authorization": "Bearer xyz"}).status_code == 401
        login = client.post("/auth/login", json={"login": "role123", "password": "Test@1234"})
        token = login.json()["access_token"]
        headers = {"Authorization": "Bearer " + token}
        assert client.get("/_test/protected", headers=headers).status_code == 200
        assert client.get("/_test/admin", headers=headers).status_code == 403


def test_reset_revokes_refresh():
    with TestClient(app) as client:
        r = client.post("/auth/register", json={
            "username": "reset123", "password": "Test@1234", "email": "reset@example.com"
        })
        assert r.status_code == 201
        first = client.post("/auth/login", json={"login": "reset123", "password": "Test@1234"}).json()
        with patch("Services.PasswordService.secrets.token_urlsafe", return_value="test-reset-once-token"):
            assert client.post("/auth/forgot-password", json={"email": "reset@example.com"}).status_code == 200
        done = client.post("/auth/reset-password", json={
            "token": "test-reset-once-token", "new_password": "NewReset@1234", "confirm_password": "NewReset@1234"
        })
        assert done.status_code == 200, done.text
        assert client.post("/auth/refresh", json={"refresh_token": first["refresh_token"]}).status_code == 401
```

BE/tests/test_modules.py
```
"""Integration smoke tests for TODO modules 0,2,3,4,5,6 and optional ERD extras."""
import json
from sqlalchemy import select
from fastapi.testclient import TestClient
from database import SessionLocal
from main import app
from Models.Users import User


def new_user(client, username, email):
    response=client.post('/auth/register',json={'username':username,'password':'Test@2026','email':email})
    assert response.status_code==201,response.text
    login=client.post('/auth/login',json={'login':username,'password':'Test@2026'})
    assert login.status_code==200,login.text
    return {'Authorization':'Bearer '+login.json()['access_token']},response.json()['id']


def test_01_users_and_roles():
    with TestClient(app) as client:
        assert client.get('/users/me').status_code==401
        headers,user_id=new_user(client,'modules2026','modules@example.com')
        me=client.get('/users/me',headers=headers)
        assert me.status_code==200,me.text
        assert me.json()['role']=='USER'
        assert client.patch('/users/me',headers=headers,json={'full_name':'Nguyễn Văn A','avatar_url':'https://example.org/avatar.png'}).status_code==200
        assert client.get('/users/me',headers=headers).json()['full_name']=='Nguyễn Văn A'
        assert client.get('/users',headers=headers).status_code==403
        assert client.post('/categories',headers=headers,json={'name':'Sorting','slug':'sorting'}).status_code==403
        with SessionLocal() as db:
            user=db.get(User,user_id);user.role='ADMIN';db.commit()
        users=client.get('/users',headers=headers)
        assert users.status_code==200,users.text
        assert any(x['id']==user_id for x in users.json()['data'])
        assert client.patch(f'/users/{user_id}/role',headers=headers,json={'role':'USER'}).status_code==409


def admin_token(client):
    response=client.post('/auth/login',json={'login':'modules2026','password':'Test@2026'})
    assert response.status_code==200,response.text
    return {'Authorization':'Bearer '+response.json()['access_token']}


def test_02_categories_algorithms_home_and_search():
    with TestClient(app) as client:
        admin=admin_token(client)
        c=client.post('/categories',headers=admin,json={'name':'Sắp xếp','slug':'sorting','description':'Kiến thức'})
        assert c.status_code==201,c.text
        category_id=c.json()['id']
        assert client.post('/categories',headers=admin,json={'name':'Sắp xếp','slug':'sorting'}).status_code==409
        p={'slug':'bubble-sort','category_id':category_id,'difficulty':'EASY','name':'Sắp xếp nổi bọt',
           'summary':'Giải thích thuật toán nổi bọt', 'theory':'Sắp xếp bằng cách hoán đổi',
           'pseudocode':'WHILE not sorted',
           'complexity':{'time_best':'O(n)','time_average':'O(n^2)','time_worst':'O(n^2)','space':'O(1)'},
           'has_simulation':True, 'code_samples':[{'language':'python','code':'print(1)'}],
           'tags':['Thuật toán sắp xếp','Mảng'],
           'examples':[{'title':'Mảng mẫu','input_data':'[3,2,1]','expected_output':'[1,2,3]','explanation':'Hoán đổi'}],
           'diagrams':[{'title':'Flowchart','diagram_type':'mermaid','source_text':'flowchart TD;A-->B'}],
           'visualization_config':{'renderer_key':'bubble-sort','config_json':'{}'}}
        r=client.post('/algorithms',headers=admin,json=p)
        assert r.status_code==201,r.text
        alg_id=r.json()['id']
        assert len(r.json()['code_samples'])==1
        assert len(r.json()['examples'])==1
        assert r.json()['visualization_config']['renderer_key']=='bubble-sort'
        assert client.post('/algorithms',headers=admin,json=p).status_code==409
        assert client.get('/algorithms/bubble-sort',headers=admin).status_code==200
        assert client.get('/algorithms',headers=admin).json()['meta']['total']>=1
        assert client.get('/search',headers=admin,params={'q':'noi bot'}).json()['data'][0]['slug']=='bubble-sort'
        assert client.get('/search/suggestions',headers=admin,params={'q':'thuật toán'}) .status_code==200
        assert client.delete(f'/categories/{category_id}',headers=admin).status_code==409
        h=client.get('/home',headers=admin)
        assert h.status_code==200,h.text
        assert h.json()['stats']['algorithms']>=1
        banner=client.post('/home/banners',headers=admin,json={'title':'Banner demo','image_url':'/img/a.svg','link_url':'/algorithms/bubble-sort'})
        assert banner.status_code==201,banner.text
        assert client.get('/home',headers=admin).json()['banners'][0]['title']=='Banner demo'


def test_03_comments_ratings_and_learning():
    with TestClient(app) as client:
        user,id=new_user(client,'learner2026','learner@example.com')
        aid=client.get('/algorithms/bubble-sort',headers=user).json()['id']
        root=client.post(f'/algorithms/{aid}/comments',headers=user,json={'content':'Rất hay!'})
        assert root.status_code==201,root.text
        rootid=root.json()['id']
        child=client.post(f'/algorithms/{aid}/comments',headers=user,json={'content':'Đúng vậy','parent_id':rootid})
        assert child.status_code==201,child.text
        assert client.get(f'/comments/{rootid}/replies',headers=user).json()['meta']['total']==1
        assert client.get(f'/algorithms/{aid}/comments',headers=user).json()['meta']['total']==1
        assert client.put(f'/comments/{rootid}',headers=user,json={'content':'<script>alert(1)</script>'}).status_code==200
        assert '<script>' not in client.get(f'/algorithms/{aid}/comments',headers=user).json()['data'][0]['content']
        rating=client.put(f'/algorithms/{aid}/rating',headers=user,json={'score':5})
        assert rating.status_code==200,rating.text
        assert rating.json()['rating_count']==1
        assert client.put(f'/algorithms/{aid}/rating',headers=user,json={'score':4}).json()['rating_count']==1
        assert client.put(f'/algorithms/{aid}/rating',headers=user,json={'score':7}).status_code==400
        assert client.post(f'/algorithms/{aid}/favorite',headers=user).status_code==200
        assert client.get('/users/me/favorites',headers=user).json()['meta']['total']==1
        assert client.put(f'/algorithms/{aid}/progress',headers=user,json={'status':'COMPLETED','progress_percent':100}).status_code==200
        assert client.get(f'/algorithms/{aid}/progress',headers=user).json()['status']=='COMPLETED'
        assert client.delete(f'/comments/{rootid}',headers=user).status_code==204
        assert client.get(f'/algorithms/{aid}/comments',headers=user).json()['meta']['total']==0
        assert client.get(f'/algorithms/{aid}',headers=user).json()['comment_count']==0
        assert client.delete(f'/algorithms/{aid}/rating',headers=user).status_code==204
        assert client.get(f'/algorithms/{aid}/rating',headers=user).json()['rating_count']==0
        assert client.delete(f'/algorithms/{aid}/favorite',headers=user).status_code==204
        assert client.get('/users/me/favorites',headers=user).json()['meta']['total']==0


def test_04_user_permissions_and_soft_delete():
    with TestClient(app) as client:
        user,_=new_user(client,'other2026','other@example.com')
        admin=admin_token(client)
        a=client.get('/algorithms/bubble-sort',headers=user).json()
        assert client.delete(f"/algorithms/{a['id']}",headers=user).status_code==403
        assert client.get('/home').status_code==401
        assert client.delete(f"/algorithms/{a['id']}",headers=admin).status_code==204
        assert client.get('/algorithms/bubble-sort',headers=user).status_code==404
        assert client.get('/search',headers=user,params={'q':'noi bot'}).json()['meta']['total']==0
        assert client.get('/home',headers=user).status_code==200


def test_05_validation_authorization_and_other_user():
    with TestClient(app) as client:
        user,_=new_user(client,'moderator2026','mod@example.com')
        admin=admin_token(client)
        me=client.patch('/users/me',headers=user,json={'role':'ADMIN'})
        assert me.status_code==400,me.text
        assert client.get('/users',headers=user).status_code==403
        assert client.get('/search',params={'q':'abc'}).status_code==401
        assert client.get('/search',headers=user,params={'q':'%'}).status_code==200
        # Create another algorithm for a foreign-comment integrity check.
        cat=client.get('/categories',headers=admin).json()[0]
        r=client.post('/algorithms',headers=admin,json={
           'slug':'second-algorithm','category_id':cat['id'],'difficulty':'EASY','name':'Thuật toán hai',
           'summary':'Một ví dụ khác','theory':'Lý thuyết','pseudocode':'Pseudocode',
           'complexity':{'time_best':'O(1)','time_average':'O(1)','time_worst':'O(1)','space':'O(1)'}})
        assert r.status_code==201,r.text
        second_id=r.json()['id']
        parent=client.post(f'/algorithms/{second_id}/comments',headers=user,json={'content':'Comment gốc'})
        assert parent.status_code==201
        wrong=client.post('/algorithms/99999/comments',headers=user,json={'content':'Other','parent_id':parent.json()['id']})
        assert wrong.status_code==404
        another,_=new_user(client,'nomod2026','nomod@example.com')
        assert client.delete(f"/comments/{parent.json()['id']}",headers=another).status_code==403
        assert client.delete(f"/comments/{parent.json()['id']}",headers=admin).status_code==204
        assert client.get(f"/comments/{parent.json()['id']}/replies",headers=user).status_code==404
        assert client.put(f'/algorithms/{second_id}/progress',headers=user,json={'status':'COMPLETED','progress_percent':50}).status_code==400
        assert client.put(f'/algorithms/{second_id}/progress',headers=user,json={'status':'IN_PROGRESS','progress_percent':50}).status_code==200
        assert client.put(f'/algorithms/{second_id}/rating',headers=user,json={'score':5}).status_code==200
        assert client.put(f'/algorithms/{second_id}/rating',headers=another,json={'score':3}).status_code==200
        stats=client.get(f'/algorithms/{second_id}/rating',headers=admin).json()
        assert stats['avg_rating']==4.0 and stats['rating_count']==2
        assert stats['distribution']['3']==1 and stats['distribution']['5']==1


def test_06_mock_smtp_service_without_network():
    """Tests SMTP handshake without real credentials or outgoing messages."""
    import os
    from unittest.mock import patch,MagicMock
    from Services.MailService import MailService
    env={'SMTP_HOST':'smtp.example.invalid','SMTP_PORT':'587','SMTP_SSL':'false',
         'SMTP_FROM':'noreply@example.invalid','SMTP_USERNAME':'noreply@example.invalid',
         'SMTP_PASSWORD':'test-placeholder-only'}
    with patch.dict(os.environ,env,clear=False):
        service=MailService()
        with patch('Services.MailService.smtplib.SMTP') as server:
            service.welcome('learner@example.invalid','Learner')
            server.assert_called_once()
            connection=server.return_value.__enter__.return_value
            connection.starttls.assert_called_once()
            connection.login.assert_called_once()
            connection.send_message.assert_called_once()
            message=connection.send_message.call_args.args[0]
            assert 'Algo_web' in str(message['Subject'])


def test_07_admin_update_content_and_cache():
    with TestClient(app) as client:
        admin=admin_token(client)
        alg=client.get('/algorithms/second-algorithm',headers=admin)
        assert alg.status_code==200,alg.text
        category=client.get('/categories',headers=admin).json()[0]
        patch={'slug':'second-algorithm','category_id':category['id'],'difficulty':'MEDIUM',
             'name':'Thuật toán đổi tên','summary':'Tìm kiếm bằng tìm chuỗi',
             'theory':'Mô tả nâng cấp','pseudocode':'new pseudocode',
             'complexity':{'time_best':'O(n)','time_average':'O(n)','time_worst':'O(n)','space':'O(1)'},
             'code_samples':[{'language':'python','code':'print("hi")'}],
             'tags':['Chuỗi'], 'has_simulation':False}
        response=client.put(f"/algorithms/{alg.json()['id']}",headers=admin,json=patch)
        assert response.status_code==200,response.text
        assert response.json()['difficulty']=='MEDIUM'
        assert response.json()['code_samples'][0]['language']=='python'
        assert client.get('/search',headers=admin,params={'q':'chuoi'}).json()['meta']['total']>=1
        assert client.get('/home',headers=admin).status_code==200
        banners=client.get('/home/banners',headers=admin).json()
        b=banners[0]
        updated=client.put(f"/home/banners/{b['id']}",headers=admin,
            json={'title':'Updated Banner','image_url':'/img/b.svg','link_url':'/algorithms/second-algorithm'})
        assert updated.status_code==200,updated.text
        assert client.get('/home',headers=admin).json()['banners'][0]['title']=='Updated Banner'
        assert client.delete(f"/home/banners/{b['id']}",headers=admin).status_code==204
        assert client.get('/home',headers=admin).json()['banners']==[]
        assert client.post('/algorithms',headers=admin,json={**patch,'slug':'wrong-json',
            'visualization_config':{'renderer_key':'a','config_json':'not-json'}}).status_code==400


def test_08_repeat_put_same_code_language_and_visualization():
    with TestClient(app) as client:
        admin=admin_token(client)
        a=client.get('/algorithms/second-algorithm',headers=admin)
        assert a.status_code==200
        item=a.json()
        payload={'slug':'second-algorithm','category_id':item['category_id'],
                 'difficulty':'MEDIUM','name':'Thuật toán đổi tên','summary':'Tìm kiếm bằng tìm chuỗi',
                 'theory':'Mô tả nâng cấp','pseudocode':'new pseudocode',
                 'complexity':{'time_best':'O(n)','time_average':'O(n)','time_worst':'O(n)','space':'O(1)'},
                 'code_samples':[{'language':'python','code':'print("updated")'}],
                 'tags':['Chuỗi'],'has_simulation':True,
                 'visualization_config':{'renderer_key':'visualizer-v1','config_json':'{"speed":1}'}}
        for i in range(2):
            payload['visualization_config']['renderer_key']=f'visualizer-v{i+1}'
            r=client.put(f"/algorithms/{item['id']}",headers=admin,json=payload)
            assert r.status_code==200,r.text
            assert len(r.json()['code_samples'])==1
            assert r.json()['code_samples'][0]['code']=='print("updated")'
            assert r.json()['visualization_config']['renderer_key']==f'visualizer-v{i+1}'
```

BE/tests/test_zz_hardening.py
```
"""Regression tests for response contracts, caching and defensive settings."""
from fastapi.testclient import TestClient
from main import app
from database import SessionLocal
from Models.Users import User
from Services.HomeCache import invalidate, get_or_build
from Services.AlgorithmService import AlgorithmService
from sqlalchemy import select


def _admin(client, username, email):
    r = client.post('/auth/register', json={
        'username': username, 'email': email, 'password': 'Test@2026'
    })
    assert r.status_code == 201, r.text
    with SessionLocal() as session:
        user = session.scalar(select(User).where(User.username == username))
        user.role = 'ADMIN'
        session.commit()
    login = client.post('/auth/login', json={'login': username, 'password': 'Test@2026'})
    assert login.status_code == 200, login.text
    return {'Authorization': 'Bearer ' + login.json()['access_token']}


def test_openapi_responses_match_actual_validation_status():
    with TestClient(app) as client:
        schema = client.get('/openapi.json').json()
        assert schema['info']['version'] == '2.1.0'
        for path, operations in schema['paths'].items():
            if path.startswith('/_test/'):
                continue
            for method, desc in operations.items():
                if method in ('delete',):
                    continue
                if method not in ('get', 'post', 'put', 'patch'):
                    continue
                assert '200' in desc['responses'] or '201' in desc['responses'], (path, method)
                assert '422' not in desc['responses'], (path, method)
        # All success responses are typed, not generic Swagger success examples.
        for route in app.routes:
            if getattr(route, 'path', '').startswith(('/_test/', '/docs', '/redoc', '/openapi.json')):
                continue
            if getattr(route, 'response_model', None) is None and getattr(route, 'methods', set()) & {'GET','POST','PUT','PATCH'}:
                assert False, f'Missing response_model: {route.path}'
        invalid = client.post('/auth/register', content='{"username"abc"}',
                              headers={'Content-Type': 'application/json'})
        assert invalid.status_code == 400
        assert 'detail' in invalid.json()


def test_security_headers_and_restricted_cors():
    with TestClient(app) as client:
        result = client.get('/users/me', headers={'Origin': 'http://localhost:5173'})
        assert result.status_code == 401
        assert result.headers['x-content-type-options'] == 'nosniff'
        assert result.headers['x-frame-options'] == 'DENY'
        assert result.headers['cache-control'] == 'no-store'
        assert result.headers.get('access-control-allow-origin') == 'http://localhost:5173'
        external = client.get('/users/me', headers={'Origin': 'https://untrusted.example'})
        assert external.headers.get('access-control-allow-origin') is None


def test_public_catalog_cache_invalidated_on_admin_change(monkeypatch):
    with TestClient(app) as client:
        admin = _admin(client, 'cache2026', 'cache@example.com')
        invalidate()
        calls = []
        original = AlgorithmService._list_algorithms_uncached

        def counted(self, *args):
            calls.append(True)
            return original(self, *args)

        monkeypatch.setattr(AlgorithmService, '_list_algorithms_uncached', counted)
        assert client.get('/algorithms', headers=admin).status_code == 200
        assert client.get('/algorithms', headers=admin).status_code == 200
        assert len(calls) == 1, 'Second list request should use cache'
        c = client.post('/categories', headers=admin, json={'name':'Kiểm thử cache', 'slug':'kiem-thu-cache'})
        assert c.status_code == 201, c.text
        assert client.get('/algorithms', headers=admin).status_code == 200
        assert len(calls) == 2, 'Admin change should invalidate list cache'
        assert any(c['slug'] == 'kiem-thu-cache' for c in client.get('/categories', headers=admin).json())


def test_admin_html_sanitization_preserves_code():
    with TestClient(app) as client:
        admin = _admin(client, 'html2026', 'html@example.com')
        category = client.post('/categories', headers=admin, json={'name':'HTML security','slug':'html-security'})
        assert category.status_code == 201, category.text
        payload = {
            'slug':'html-example', 'category_id':category.json()['id'], 'difficulty':'EASY',
            'name':'Ví dụ bảo mật', 'summary':'<img src=x onerror=alert(1)>Mô tả',
            'theory':'<script>alert(1)</script><strong>Văn bản an toàn</strong>',
            'pseudocode':'IF a < b', 'has_simulation': False,
            'complexity':{'time_best':'O(1)','time_average':'O(1)','time_worst':'O(1)','space':'O(1)'},
            'code_samples':[{'language':'python','code':'if a < b:\n    print(a)'}]
        }
        r = client.post('/algorithms', headers=admin, json=payload)
        assert r.status_code == 201, r.text
        body = r.json()
        assert '<script>' not in body['theory']
        assert '<strong>' in body['theory']
        assert '<img' not in body['summary']
        assert 'if a < b' in body['code_samples'][0]['code']
        details = client.get('/algorithms/html-example', headers=admin)
        assert details.status_code == 200
        assert '<script>' not in details.json()['theory']


def test_redis_cache_invalidation_in_shared_mode(monkeypatch):
    import Services.HomeCache as cache
    store = {}

    class FakeRedis:
        def get(self, key):
            return store.get(key)
        def set(self, key, value, ex=None):
            store[key] = value
        def incr(self, key):
            n=int(store.get(key, '0'))+1
            store[key] = str(n)
            return n

    monkeypatch.setattr(cache, 'redis_client', lambda: FakeRedis())
    counter = []

    def build():
        counter.append(1)
        return {'value': len(counter)}

    assert cache.get_or_build(build, key='fake-test')['value'] == 1
    assert cache.get_or_build(build, key='fake-test')['value'] == 1
    cache.invalidate()
    assert cache.get_or_build(build, key='fake-test')['value'] == 2


def test_redis_rate_limit_shared_mode(monkeypatch):
    import Services.RateLimiter as limiter
    from Services.AuthError import AuthError
    calls = {}

    class FakeRedis:
        def eval(self, code, numkeys, key, ttl):
            calls[key] = calls.get(key, 0) + 1
            return calls[key]
        def delete(self, key):
            calls.pop(key, None)

    monkeypatch.setattr(limiter, 'redis_client', lambda: FakeRedis())
    limit = limiter.RateLimiter()
    limit.check('user:12', 2, 60)
    limit.check('user:12', 2, 60)
    try:
        limit.check('user:12', 2, 60)
        assert False, 'Expected rate limit error'
    except AuthError as exc:
        assert exc.status_code == 429
    limit.clear('user:12')
    limit.check('user:12', 2, 60)


def test_untrusted_links_and_large_escaped_comments_rejected():
    with TestClient(app) as client:
        admin = _admin(client, 'safeurl2026', 'safeurl@example.com')
        bad_banner = client.post('/home/banners', headers=admin, json={
            'title':'Không an toàn','image_url':'/assets/preview.svg',
            'link_url':'javascript:alert(1)',
        })
        assert bad_banner.status_code == 400, bad_banner.text
        bad_profile = client.patch('/users/me', headers=admin, json={
            'avatar_url':'data:text/html,<script>alert(1)</script>'
        })
        assert bad_profile.status_code == 400, bad_profile.text
        category = client.post('/categories', headers=admin, json={
            'name':'Kiểm thử URL','slug':'kiem-thu-url'
        })
        assert category.status_code == 201, category.text
        alg = client.post('/algorithms', headers=admin, json={
            'slug':'test-encoded-length','category_id':category.json()['id'],
            'name':'Kiểm thử ký tự HTML','difficulty':'EASY',
            'summary':'Thử nghiệm nội dung bình luận','theory':'Lý thuyết ngắn',
            'pseudocode':'return n',
            'complexity':{'time_best':'O(1)','time_average':'O(1)','time_worst':'O(1)','space':'O(1)'}
        })
        assert alg.status_code == 201, alg.text
        # Input is 500 chars, but &lt; encoding would exceed the DB's 1000-char CHECK.
        comment = client.post(f"/algorithms/{alg.json()['id']}/comments", headers=admin,
                              json={'content':'<'*500})
        assert comment.status_code == 400, comment.text
```

BE/tests/test_zz_mail.py
```
"""SMTP and reset-link tests without external network calls."""
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from main import app
from Services.MailService import MailService


def test_welcome_and_reset_email_templates_with_sandbox_settings(monkeypatch):
    monkeypatch.setenv('SMTP_HOST', 'sandbox.smtp.mailtrap.io')
    monkeypatch.setenv('SMTP_PORT', '587')
    monkeypatch.setenv('SMTP_SSL', 'false')
    monkeypatch.setenv('SMTP_FROM', 'algoweb2026@gmail.com')
    monkeypatch.setenv('SMTP_USERNAME', 'test-sandbox-login')
    monkeypatch.setenv('SMTP_PASSWORD', 'test-sandbox-secret')
    monkeypatch.setenv('FRONTEND_RESET_PASSWORD_URL', 'http://localhost:5173/reset-password')
    smtp=MagicMock()
    # The context manager returns our fake SMTP session; never uses Internet.
    smtp.__enter__.return_value=smtp
    with patch('Services.MailService.smtplib.SMTP',return_value=smtp) as sender:
        mail=MailService()
        assert mail.enabled
        mail.welcome('demo@example.com','demo2026')
        mail.reset_link('demo@example.com','test-only-token')
        mail.password_changed('demo@example.com')
        assert sender.call_count==3
        assert smtp.starttls.call_count==3
        assert smtp.login.call_count==3
        assert smtp.send_message.call_count==3
        args=[x.args[0] for x in smtp.send_message.call_args_list]
        assert 'Chào mừng bạn' in args[0]['Subject']
        assert 'token=test-only-token' in args[1].get_content()
        assert '20 phút' in args[1].get_content()
        assert 'Mật khẩu' in args[2]['Subject']
        assert all('test-sandbox-secret' not in msg.get_content() for msg in args)


def test_forgot_password_does_not_expose_token_in_http_response():
    with TestClient(app) as client:
        result=client.post('/auth/forgot-password',json={'email':'not-registered@example.com'})
        assert result.status_code==200
        assert list(result.json())==['message']
        assert 'token' not in result.text.lower()
```

FE/src/App.css
```
:root {
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  color: #e8edf8;
  background: #0b1020;
  font-synthesis: none;
  text-rendering: optimizeLegibility;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  font-optical-sizing: auto;
  font-weight: 400;
  --canvas: #0b1020;
  --sidebar: #0f1729;
  --surface: #141e31;
  --raised: #1a263d;
  --line: #ffffff14;
  --muted: #8b9ab4;
  --faint: #64728b;
  --violet: #9b7afa;
  --cyan: #5ed9e6;
}

* {
  box-sizing: border-box;
}

body {
  min-width: 320px;
  min-height: 100vh;
  margin: 0;
  background:
    radial-gradient(ellipse at 100% 0, #06b6d40a, transparent 34%),
    radial-gradient(ellipse at 25% 30%, #8b5cf606, transparent 32%),
    var(--canvas);
}

button,
input,
textarea,
select {
  font: inherit;
}

button,
a,
input,
textarea,
select {
  -webkit-tap-highlight-color: transparent;
}

button,
select {
  cursor: pointer;
}

button:disabled {
  cursor: not-allowed;
  opacity: 0.62;
}

a {
  color: inherit;
  text-decoration: none;
}

button:focus-visible,
a:focus-visible,
input:focus-visible,
textarea:focus-visible,
select:focus-visible {
  outline: 2px solid #a78bfa;
  outline-offset: 3px;
}

.night-sky-canvas {
  position: fixed;
  inset: 0;
  z-index: -1;
  display: block;
  width: 100%;
  height: 100%;
  pointer-events: none;
  background: radial-gradient(ellipse at 50% 110%, #0d1d38 0%, #050a16 60%, #03050c 100%);
}

.auth-page,
.session-loading {
  display: grid;
  min-height: 100vh;
  place-items: center;
  padding: 2rem 1rem;
}

.auth-card {
  width: min(100%, 27rem);
  padding: 2.2rem;
  border: 1px solid var(--line);
  border-radius: 1rem;
  background: linear-gradient(145deg, #172139f2, #111a2df5);
  box-shadow: 0 24px 90px #0006;
}

.auth-header {
  margin-bottom: 1.5rem;
}

.auth-header h1 {
  margin: 0;
  font-size: 1.8rem;
  font-weight: 650;
  letter-spacing: -0.045em;
}

.auth-header p,
.field-hint {
  color: var(--muted);
  line-height: 1.55;
}

.auth-header p {
  margin: 0.55rem 0 0;
}

.auth-tabs {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.25rem;
  margin-bottom: 1.5rem;
  padding: 0.25rem;
  border: 1px solid var(--line);
  border-radius: 0.6rem;
  background: #0c1424;
}

.auth-tab {
  min-height: 2.55rem;
  border: 0;
  border-radius: 0.4rem;
  background: transparent;
  color: var(--muted);
  cursor: pointer;
}

.auth-tab.is-active {
  background: #8b5cf62b;
  color: #d7c6ff;
}

.auth-form,
.profile-form {
  display: grid;
  gap: 1rem;
}

.form-field,
.profile-form label,
.sim-inputs label,
.filter-row label {
  display: grid;
  gap: 0.45rem;
  color: #cbd4e4;
  font-size: 0.88rem;
  font-weight: 550;
}

.form-field input,
.profile-form input,
.sim-inputs input,
.filter-row select,
.comment-form textarea {
  width: 100%;
  min-height: 2.8rem;
  padding: 0.65rem 0.75rem;
  border: 1px solid #ffffff20;
  border-radius: 0.5rem;
  background: #0d1729;
  color: #edf2ff;
  font-weight: 400;
}

.form-field input:focus,
.profile-form input:focus,
.sim-inputs input:focus,
.comment-form textarea:focus {
  border-color: #9b7afa;
}

.form-field input::placeholder,
.comment-form textarea::placeholder {
  color: #71809a;
}

.field-hint {
  font-size: 0.76rem;
  font-weight: 400;
}

.remember-field {
  display: flex;
  align-items: center;
  gap: 0.55rem;
  color: var(--muted);
  font-size: 0.82rem;
}

.remember-field input {
  accent-color: #8b5cf6;
}

.submit-button,
.primary-button,
.secondary-button {
  display: inline-flex;
  min-height: 2.7rem;
  align-items: center;
  justify-content: center;
  gap: 0.6rem;
  padding: 0.65rem 1rem;
  border: 1px solid transparent;
  border-radius: 0.55rem;
  background: linear-gradient(105deg, #8256e8, #a052d5);
  color: #fff;
  cursor: pointer;
  font-size: 0.86rem;
  font-weight: 650;
  transition: filter 0.2s ease, transform 0.2s ease;
}

.submit-button:hover,
.primary-button:hover {
  filter: brightness(1.12);
}

.submit-button:disabled,
.primary-button:disabled {
  cursor: wait;
}

.secondary-button {
  border-color: var(--line);
  background: #ffffff0a;
  color: #d5c7ff;
}

.form-status,
.inline-notice,
.session-error,
.notice-error,
.sim-error {
  padding: 0.8rem 0.9rem;
  border: 1px solid #ffffff20;
  border-radius: 0.55rem;
  color: #d3dded;
  font-size: 0.88rem;
  line-height: 1.5;
  overflow-wrap: anywhere;
}

.form-status p {
  margin: 0;
}

.form-status p + p {
  margin-top: 0.4rem;
}

.is-error,
.notice-error,
.sim-error {
  border-color: #fb71854a;
  background: #fb718510;
  color: #ffc2ce;
}

.is-success,
.inline-notice {
  background: #34d3990c;
  color: #a7f3d0;
}

.text-button {
  margin-top: 0.65rem;
  padding: 0;
  border: 0;
  background: transparent;
  color: #cab7ff;
  cursor: pointer;
  font: inherit;
  font-weight: 600;
  text-decoration: underline;
  text-underline-offset: 0.15em;
}

.session-error {
  position: fixed;
  top: 1rem;
  left: 50%;
  z-index: 4;
  width: min(90vw, 36rem);
  transform: translateX(-50%);
  border-color: #fbbf2444;
  background: #35280e;
  color: #fde68a;
}

.session-loading {
  display: flex;
  gap: 0.75rem;
  color: var(--muted);
}

.loading-spinner {
  width: 1.15rem;
  height: 1.15rem;
  border: 2px solid #9b7afa44;
  border-top-color: #b59aff;
  border-radius: 50%;
  animation: spin 0.75s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.workspace {
  min-height: 100vh;
  color: #e8edf8;
}

.sidebar {
  position: fixed;
  z-index: 30;
  inset: 0 auto 0 0;
  display: flex;
  width: 250px;
  flex-direction: column;
  overflow-y: auto;
  border-right: 1px solid var(--line);
  background: var(--sidebar);
}

.brand {
  display: flex;
  height: 84px;
  flex: 0 0 auto;
  align-items: center;
  gap: 0.7rem;
  padding: 0 1.5rem;
  font-size: 1.4rem;
  font-weight: 750;
  letter-spacing: -0.06em;
}

.brand > span:last-child > span {
  color: var(--violet);
}

.brand-mark {
  display: grid;
  width: 2.45rem;
  height: 2.45rem;
  place-items: center;
  border: 1px solid #bca3ff55;
  border-radius: 0.8rem;
  background: linear-gradient(140deg, #945df0, #5c40c1);
  box-shadow: 0 0 22px #8b5cf630;
  font-size: 1.3rem;
}

.nav-caption {
  margin: 1.1rem 1.5rem 0.8rem;
  color: #64728b;
  font-size: 0.63rem;
  font-weight: 700;
  letter-spacing: 0.14em;
}

.side-nav {
  display: grid;
  gap: 0.35rem;
  padding: 0 1rem;
}

.side-nav a {
  display: flex;
  min-height: 2.7rem;
  align-items: center;
  gap: 0.8rem;
  padding: 0.6rem 0.8rem;
  border-radius: 0.55rem;
  color: #a0acc2;
  font-size: 0.82rem;
  transition: background 0.18s ease, color 0.18s ease;
}

.side-nav a:hover,
.side-nav a.nav-active {
  background: linear-gradient(100deg, #7548dc, #7850d2);
  color: white;
}

.side-nav a.nav-child,
.side-nav a.nav-child-active {
  min-height: 2.3rem;
  padding-left: 1.25rem;
  font-size: 0.76rem;
}

.side-nav a.nav-child-active {
  color: #d4c4ff;
}

.nav-dot,
.eyebrow > span {
  width: 0.4rem;
  height: 0.4rem;
  flex: 0 0 auto;
  border-radius: 50%;
  background: #8b74ef;
}

.sidebar-bottom {
  margin-top: auto;
  padding: 1.2rem;
}

.learning-tip {
  padding: 1rem;
  border: 1px solid #9e7bfa24;
  border-radius: 0.8rem;
  background: linear-gradient(140deg, #8b5cf616, transparent);
}

.learning-tip > span {
  display: block;
  margin-bottom: 0.6rem;
  color: var(--violet);
}

.learning-tip strong,
.sidebar-user strong {
  display: block;
  font-size: 0.75rem;
}

.learning-tip p {
  margin: 0.5rem 0;
  color: var(--faint);
  font-size: 0.72rem;
  line-height: 1.5;
}

.learning-tip a {
  color: #c4b5fd;
  font-size: 0.72rem;
}

.sidebar-user {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px solid var(--line);
}

.sidebar-user small,
.account-label {
  color: var(--muted);
  font-size: 0.67rem;
}

.avatar,
.avatar-large {
  display: grid;
  width: 2.25rem;
  height: 2.25rem;
  flex: 0 0 auto;
  place-items: center;
  border: 1px solid #b79aff44;
  border-radius: 50%;
  background: linear-gradient(145deg, #855be3, #385c7d);
  color: white;
  font-size: 0.85rem;
  font-weight: 700;
}

.workspace-main {
  min-height: 100vh;
  margin-left: 250px;
}

.topbar {
  position: sticky;
  z-index: 20;
  top: 0;
  display: flex;
  min-height: 76px;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.8rem clamp(1rem, 3vw, 2.3rem);
  border-bottom: 1px solid var(--line);
  background: #0d1526e8;
  backdrop-filter: blur(16px);
}

.topbar-title,
.topbar-actions,
.account-button {
  display: flex;
  align-items: center;
}

.topbar-title {
  min-width: 0;
  gap: 0.8rem;
}

.topbar-title h1 {
  overflow: hidden;
  margin: 0;
  font-size: 0.96rem;
  font-weight: 650;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.workspace-badge,
.sim-local-badge {
  padding: 0.35rem 0.55rem;
  border: 1px solid #9e7bfa24;
  border-radius: 0.4rem;
  background: #8b5cf610;
  color: #bba8ff;
  font-size: 0.63rem;
  white-space: nowrap;
}

.topbar-actions {
  gap: 1rem;
}

.search-box {
  position: relative;
  display: flex;
  width: min(27vw, 17rem);
  min-width: 12rem;
  height: 2.5rem;
  align-items: center;
  gap: 0.55rem;
  padding: 0 0.65rem;
  border: 1px solid var(--line);
  border-radius: 0.55rem;
  background: #ffffff08;
}

.search-icon {
  color: var(--muted);
  font-size: 1.3rem;
  line-height: 1;
}

.search-box input {
  width: 100%;
  min-width: 0;
  border: 0;
  outline: 0;
  background: transparent;
  color: #e8edf8;
  font-size: 0.75rem;
}

.search-box input:focus-visible {
  outline: 0;
}

.search-box kbd {
  padding: 0.2rem 0.3rem;
  border: 1px solid var(--line);
  border-radius: 0.25rem;
  color: var(--muted);
  font-size: 0.58rem;
  white-space: nowrap;
}

.suggestion-menu,
.account-menu {
  position: absolute;
  z-index: 40;
  top: calc(100% + 0.45rem);
  right: 0;
  width: max(100%, 16rem);
  padding: 0.4rem;
  border: 1px solid var(--line);
  border-radius: 0.7rem;
  background: var(--raised);
  box-shadow: 0 16px 40px #0006;
}

.suggestion-menu a,
.suggestion-menu button,
.account-menu a,
.account-menu button {
  display: flex;
  width: 100%;
  align-items: center;
  justify-content: space-between;
  padding: 0.7rem;
  border: 0;
  border-radius: 0.45rem;
  background: transparent;
  color: #dce5f5;
  cursor: pointer;
  font-size: 0.75rem;
  text-align: left;
}

.suggestion-menu a:hover,
.suggestion-menu button:hover,
.account-menu a:hover,
.account-menu button:hover {
  background: #ffffff0b;
}

.account-wrap {
  position: relative;
}

.account-button {
  gap: 0.6rem;
  padding: 0.2rem;
  border: 0;
  background: transparent;
  color: #dce5f5;
}

.account-label {
  max-width: 8rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.account-menu {
  width: 12rem;
}

.mobile-menu {
  display: none;
  border: 0;
  background: transparent;
  color: #dce5f5;
  font-size: 1.1rem;
}

.workspace-content {
  width: min(100%, 1510px);
  min-height: calc(100vh - 130px);
  margin: 0 auto;
  padding: 1.75rem clamp(1rem, 3vw, 2.3rem);
}

.workspace-footer {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  margin: 0 clamp(1rem, 3vw, 2.3rem);
  padding: 1rem 0;
  border-top: 1px solid var(--line);
  color: #64728b;
  font-size: 0.67rem;
}

.loading-state {
  display: flex;
  min-height: 15rem;
  align-items: center;
  justify-content: center;
  gap: 0.7rem;
  color: var(--muted);
  font-size: 0.85rem;
}

.notice-error {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1rem;
}

.notice-error button {
  border: 0;
  background: transparent;
  color: inherit;
  font-size: 1.1rem;
}

.page-enter {
  animation: page-enter 0.35s ease-out both;
}

@keyframes page-enter {
  from { opacity: 0; transform: translateY(7px); }
  to { opacity: 1; transform: translateY(0); }
}

.hero-panel {
  position: relative;
  isolation: isolate;
  overflow: hidden;
  min-height: 19rem;
  padding: clamp(1.6rem, 4vw, 2.6rem);
  border: 1px solid #a78bfa32;
  border-radius: 1.15rem;
  background: linear-gradient(112deg, #2d1c4b 0%, #242044 40%, #123343 100%);
}

.hero-panel::after {
  position: absolute;
  z-index: -1;
  top: -40%;
  right: -3%;
  width: 22rem;
  height: 22rem;
  border: 1px solid #a78bfa30;
  border-radius: 50%;
  background: radial-gradient(circle, #9b7afa20, transparent 65%);
  content: "";
}

.eyebrow {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: #c8b7ff;
  font-size: 0.67rem;
  font-weight: 650;
  letter-spacing: 0.09em;
}

.hero-panel h2 {
  max-width: 38rem;
  margin: 1rem 0 0;
  font-size: clamp(2rem, 4vw, 2.8rem);
  font-weight: 650;
  letter-spacing: -0.055em;
  line-height: 1.15;
}

.hero-panel > p {
  max-width: 31rem;
  margin: 1rem 0 0;
  color: #c3cada;
  font-size: 0.9rem;
  line-height: 1.7;
}

.hero-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 1.2rem;
  margin-top: 1.5rem;
}

.quiet-link,
.section-heading > a {
  color: #c7b5ff;
  font-size: 0.78rem;
}

.hero-orbit {
  position: absolute;
  right: 8%;
  bottom: 12%;
  display: grid;
  width: 12rem;
  height: 12rem;
  place-items: center;
  border: 1px solid #b3a1ff39;
  border-radius: 50%;
  color: #cfc5ff;
  font-family: ui-monospace, monospace;
  font-size: 0.8rem;
  transform: rotate(-16deg);
}

.hero-orbit::before,
.hero-orbit::after {
  position: absolute;
  inset: 1.3rem;
  border: 1px dashed #7dd3fc43;
  border-radius: 50%;
  content: "";
}

.hero-orbit::after {
  inset: 2.9rem;
  border-style: solid;
  border-color: #b994ff5e;
}

.hero-orbit i,
.hero-orbit b,
.hero-orbit em {
  position: absolute;
  width: 0.6rem;
  height: 0.6rem;
  border-radius: 50%;
  background: #81e3eb;
  box-shadow: 0 0 15px #67e8f9;
}

.hero-orbit i { top: 1.7rem; right: 3rem; }
.hero-orbit b { bottom: 2.2rem; left: 1.5rem; background: #c084fc; }
.hero-orbit em { right: 1.7rem; bottom: 2.5rem; background: #f0abfc; }

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0.9rem;
  margin-top: 1rem;
}

.stat-card,
.content-panel {
  border: 1px solid var(--line);
  border-radius: 0.85rem;
  background: linear-gradient(140deg, #141e31, #111a2b);
}

.stat-card {
  display: grid;
  gap: 0.2rem;
  padding: 1.1rem;
}

.stat-card strong {
  font-size: 1.6rem;
  letter-spacing: -0.04em;
}

.stat-card > span {
  color: #d3dced;
  font-size: 0.75rem;
}

.stat-card small {
  margin-top: 0.3rem;
  color: var(--faint);
  font-size: 0.66rem;
}

.banner-strip {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(13rem, 1fr));
  gap: 0.75rem;
  margin-top: 1.2rem;
}

.banner-strip a {
  display: flex;
  justify-content: space-between;
  padding: 0.9rem 1rem;
  border: 1px solid #9b7afa33;
  border-radius: 0.65rem;
  background: #8b5cf610;
  color: #d5c7ff;
  font-size: 0.8rem;
}

.workspace-section {
  margin-top: 2.25rem;
}

.section-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1rem;
}

.section-heading h2,
.section-heading h3 {
  margin: 0;
  font-size: 1.1rem;
  font-weight: 650;
  letter-spacing: -0.025em;
}

.section-heading p {
  margin: 0.45rem 0 0;
  color: var(--muted);
  font-size: 0.74rem;
  line-height: 1.55;
}

.category-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0.9rem;
}

.category-card {
  min-height: 10.5rem;
  padding: 1rem;
  border: 1px solid var(--line);
  border-radius: 0.8rem;
  background: linear-gradient(145deg, #8b5cf617, var(--surface) 72%);
  transition: transform 0.2s ease, border-color 0.2s ease;
}

.category-card:hover,
.algorithm-card:hover {
  transform: translateY(-3px);
  border-color: #a78bfa63;
}

.category-card-1 { background: linear-gradient(145deg, #06b6d41b, var(--surface) 72%); }
.category-card-2 { background: linear-gradient(145deg, #10b98118, var(--surface) 72%); }
.category-card-3 { background: linear-gradient(145deg, #f9731618, var(--surface) 72%); }

.category-symbol {
  color: #c4b5fd;
  font-size: 1.4rem;
}

.category-card h3 {
  margin: 0.75rem 0 0;
  font-size: 0.86rem;
}

.category-card p {
  min-height: 2.3rem;
  margin: 0.45rem 0;
  color: var(--muted);
  font-size: 0.69rem;
  line-height: 1.55;
}

.category-card small {
  color: #bda9ff;
  font-size: 0.67rem;
}

.algorithm-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 1rem;
}

.algorithm-card {
  display: flex;
  min-height: 13rem;
  flex-direction: column;
  padding: 1rem;
  border: 1px solid var(--line);
  border-radius: 0.8rem;
  background: var(--surface);
  transition: transform 0.2s ease, border-color 0.2s ease;
}

.algorithm-card-top,
.algorithm-card-meta,
.detail-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
}

.algorithm-card-top {
  justify-content: space-between;
}

.category-chip,
.difficulty,
.tag-row span {
  padding: 0.28rem 0.48rem;
  border: 1px solid var(--line);
  border-radius: 999px;
  color: #b7c3d8;
  font-size: 0.62rem;
}

.difficulty-easy { border-color: #34d39933; background: #34d39912; color: #6ee7b7; }
.difficulty-medium { border-color: #fbbf2433; background: #fbbf2410; color: #fcd34d; }
.difficulty-hard { border-color: #fb718533; background: #fb718510; color: #fda4af; }

.algorithm-card h3 {
  margin: 0.95rem 0 0.4rem;
  font-size: 1rem;
}

.algorithm-card > p {
  display: -webkit-box;
  overflow: hidden;
  min-height: 2.4rem;
  margin: 0;
  color: var(--muted);
  font-size: 0.75rem;
  line-height: 1.6;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.algorithm-card-meta {
  margin-top: 0.85rem;
  color: #8795ad;
  font-size: 0.65rem;
}

.card-link {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: auto;
  padding-top: 0.9rem;
  color: #c7b5ff;
  font-size: 0.72rem;
}

.library-intro {
  padding: 1.5rem;
  border: 1px solid #9b7afa24;
  border-radius: 0.9rem;
  background: linear-gradient(105deg, #8b5cf61a, transparent);
}

.library-intro h2 {
  margin: 0.7rem 0 0;
  font-size: 1.8rem;
  letter-spacing: -0.045em;
}

.library-intro p {
  margin: 0.7rem 0 0;
  color: var(--muted);
  font-size: 0.82rem;
}

.filter-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.8rem;
  margin-top: 1.2rem;
}

.filter-row label {
  min-width: 12rem;
  font-size: 0.72rem;
}

.filter-row select {
  min-height: 2.5rem;
  font-size: 0.75rem;
}

.result-count {
  margin: 1.2rem 0 0.8rem;
  color: var(--muted);
  font-size: 0.72rem;
}

.empty-state {
  padding: 2rem 1rem;
  color: var(--muted);
  font-size: 0.82rem;
  text-align: center;
}

.back-link {
  display: inline-flex;
  margin-bottom: 1rem;
  color: #b9a7f8;
  font-size: 0.75rem;
}

.detail-hero {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1.5rem;
  padding: clamp(1.2rem, 3vw, 2rem);
  border: 1px solid #9b7afa30;
  border-radius: 1rem;
  background: linear-gradient(110deg, #382654, #1d2840 65%, #133241);
}

.detail-hero h2 {
  margin: 0.7rem 0;
  font-size: clamp(1.8rem, 4vw, 2.5rem);
  letter-spacing: -0.05em;
}

.detail-hero p {
  max-width: 48rem;
  color: #c0cadd;
  font-size: 0.85rem;
  line-height: 1.65;
}

.detail-meta {
  margin-top: 1rem;
  color: #c0cadd;
  font-size: 0.7rem;
}

.favorite-button {
  flex: 0 0 auto;
  padding: 0.65rem 0.8rem;
  border: 1px solid #ffffff25;
  border-radius: 0.55rem;
  background: #ffffff0b;
  color: #e9e1ff;
  font-size: 0.72rem;
}

.favorite-button.is-favorite {
  border-color: #fbbf2455;
  color: #fcd34d;
}

.simulator-panel {
  margin-top: 1rem;
  padding: 1.25rem;
  border: 1px solid var(--line);
  border-radius: 0.9rem;
  background: linear-gradient(145deg, #141e31, #111a2b);
}

.simulator-panel .section-heading {
  margin-bottom: 1.1rem;
}

.sim-inputs {
  display: flex;
  align-items: flex-end;
  gap: 0.7rem;
}

.sim-inputs label {
  flex: 1;
  min-width: 10rem;
  font-size: 0.7rem;
}

.sim-inputs input {
  min-height: 2.5rem;
  font-size: 0.72rem;
}

.sim-stage {
  min-height: 15rem;
  margin-top: 1.2rem;
  padding: 1rem;
  overflow-x: auto;
  border: 1px solid var(--line);
  border-radius: 0.7rem;
  background-color: #0c1424;
  background-image: linear-gradient(#ffffff08 1px, transparent 1px), linear-gradient(90deg, #ffffff08 1px, transparent 1px);
  background-size: 2rem 2rem;
}

.sim-bars {
  display: flex;
  min-width: 27rem;
  height: 12rem;
  align-items: flex-end;
  justify-content: center;
  gap: clamp(0.25rem, 1.2vw, 0.8rem);
  padding: 1.5rem 0 0.8rem;
  border-bottom: 1px solid #ffffff25;
}

.sim-bar-column {
  position: relative;
  display: flex;
  width: 100%;
  max-width: 3.2rem;
  height: 100%;
  flex: 1;
  align-items: flex-end;
  justify-content: center;
}

.sim-bar {
  width: 80%;
  min-height: 0.5rem;
  border: 1px solid #c4b5fd77;
  border-radius: 0.3rem 0.3rem 0 0;
  background: linear-gradient(0deg, #6d3fc9, #cb91ef);
  transition: height 0.25s ease, background 0.2s ease;
}

.sim-bar-active {
  border-color: #fda4af;
  background: linear-gradient(0deg, #be185d, #fb7185);
}

.sim-bar-sorted {
  border-color: #6ee7b7;
  background: linear-gradient(0deg, #047857, #34d399);
}

.sim-value,
.sim-bar-column small {
  position: absolute;
  left: 50%;
  color: #cbd5e1;
  font-family: ui-monospace, monospace;
  font-size: 0.62rem;
  transform: translateX(-50%);
}

.sim-value { top: -1rem; }
.sim-bar-column small { bottom: -1.1rem; color: var(--faint); }

.sim-description {
  min-height: 1.3rem;
  color: #c8d3e6;
  font-size: 0.75rem;
}

.sim-controls {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.55rem;
}

.sim-controls > button:not(.primary-button) {
  min-width: 2.4rem;
  min-height: 2.4rem;
  border: 1px solid var(--line);
  border-radius: 0.5rem;
  background: #ffffff08;
  color: #d8e0ef;
}

.sim-controls > span {
  margin-left: 0.5rem;
  color: var(--muted);
  font-size: 0.7rem;
}

.sim-graph {
  position: relative;
  display: grid;
  width: min(100%, 38rem);
  min-height: 13rem;
  grid-template-columns: repeat(3, 1fr);
  align-items: center;
  justify-items: center;
  margin: auto;
}

.graph-node {
  z-index: 1;
  display: grid;
  width: 2.8rem;
  height: 2.8rem;
  place-items: center;
  border: 1px solid #7283a3;
  border-radius: 50%;
  background: #1d2842;
  color: #e2e8f0;
}

.graph-node-active { border-color: #67e8f9; background: #0e7490; box-shadow: 0 0 20px #06b6d455; }
.graph-node-visited { border-color: #34d399; background: #154235; color: #6ee7b7; }
.graph-edge { display: none; }

.complexity-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0.7rem;
  margin-top: 1rem;
}

.complexity-grid > div {
  display: grid;
  gap: 0.5rem;
  padding: 0.9rem;
  border: 1px solid var(--line);
  border-radius: 0.65rem;
  background: var(--surface);
}

.complexity-grid small {
  color: var(--muted);
  font-size: 0.64rem;
}

.complexity-grid strong {
  color: #c7b5ff;
  font-family: ui-monospace, monospace;
  font-size: 0.9rem;
}

.detail-tabs {
  display: flex;
  gap: 0.4rem;
  margin-top: 1.2rem;
  border-bottom: 1px solid var(--line);
}

.detail-tabs button {
  padding: 0.8rem 1rem;
  border: 0;
  border-bottom: 2px solid transparent;
  background: transparent;
  color: var(--muted);
  font-size: 0.77rem;
}

.detail-tabs button[aria-selected="true"] {
  border-bottom-color: #9b7afa;
  color: #d8cbff;
}

.detail-content {
  min-height: 12rem;
  padding: 1.25rem;
  border-top-left-radius: 0;
  border-top-right-radius: 0;
}

.detail-content h3,
.example-card h4 {
  margin: 0 0 0.8rem;
  font-size: 0.95rem;
}

.prose-text {
  color: #c0cadd;
  font-size: 0.82rem;
  line-height: 1.8;
  white-space: pre-wrap;
}

.code-block {
  max-height: 30rem;
  overflow: auto;
  padding: 1rem;
  border: 1px solid var(--line);
  border-radius: 0.6rem;
  background: #0b1220;
  color: #cbd5e1;
  font-size: 0.76rem;
  line-height: 1.7;
  white-space: pre-wrap;
}

.sample-code + .sample-code { margin-top: 1rem; }
.sample-code > div { margin: 0.8rem 0; color: #bba8ff; font-size: 0.72rem; }
.tag-row { display: flex; flex-wrap: wrap; gap: 0.45rem; margin: 1rem 0; }
.tag-row span { color: #c4b5fd; }

.example-card {
  margin: 1rem 0;
  padding: 1rem;
  border: 1px solid var(--line);
  border-radius: 0.7rem;
  background: #ffffff05;
}

.example-card p,
.example-values {
  color: var(--muted);
  font-size: 0.75rem;
  line-height: 1.6;
}

.example-values {
  display: flex;
  flex-wrap: wrap;
  gap: 0.8rem;
}

.example-values code {
  color: #d8cbff;
}

.interaction-grid {
  display: grid;
  grid-template-columns: 0.8fr 1.2fr;
  gap: 1rem;
  margin-top: 1rem;
}

.rating-panel,
.comments-panel {
  padding: 1.1rem;
}

.rating-stars {
  display: flex;
  gap: 0.3rem;
}

.rating-stars button {
  border: 0;
  background: transparent;
  color: #475569;
  font-size: 1.8rem;
}

.rating-stars button.star-selected {
  color: #fbbf24;
}

.rating-distribution {
  display: flex;
  flex-wrap: wrap;
  gap: 0.55rem;
  margin-top: 0.8rem;
  color: var(--muted);
  font-size: 0.65rem;
}

.comment-form textarea {
  min-height: 5rem;
  resize: vertical;
  font-size: 0.76rem;
}

.comment-form > div {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 0.4rem;
}

.comment-form small {
  color: var(--faint);
  font-size: 0.65rem;
}

.comment-list {
  display: grid;
  gap: 0.85rem;
  margin-top: 1.2rem;
}

.comment-item {
  display: flex;
  gap: 0.7rem;
  padding-top: 0.8rem;
  border-top: 1px solid var(--line);
}

.comment-item > div { min-width: 0; flex: 1; }
.comment-heading { display: flex; align-items: center; gap: 0.6rem; }
.comment-heading strong { font-size: 0.73rem; }
.comment-heading time,
.comment-item small { color: var(--faint); font-size: 0.62rem; }
.comment-item p { margin: 0.35rem 0; color: #c0cadd; font-size: 0.75rem; line-height: 1.6; overflow-wrap: anywhere; }

.profile-panel {
  max-width: 46rem;
  padding: 1.3rem;
}

.profile-identity {
  display: flex;
  align-items: center;
  gap: 0.9rem;
  margin: 1.5rem 0;
}

.avatar-large { width: 3.3rem; height: 3.3rem; font-size: 1.2rem; }
.profile-identity strong,
.profile-identity span { display: block; }
.profile-identity strong { font-size: 0.9rem; }
.profile-identity div span { margin-top: 0.35rem; color: var(--muted); font-size: 0.68rem; }
.profile-form { max-width: 31rem; }
.profile-form label { font-size: 0.74rem; }
.profile-form input[readonly] { opacity: 0.65; }
.profile-form .primary-button { justify-self: start; margin-top: 0.3rem; }

.mobile-backdrop { display: none; }

@media (max-width: 1100px) {
  .algorithm-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .category-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .hero-orbit { right: 4%; opacity: 0.6; }
}

@media (max-width: 760px) {
  .sidebar {
    transform: translateX(-102%);
    transition: transform 0.25s ease;
  }
  .sidebar.sidebar-open { transform: translateX(0); }
  .mobile-backdrop {
    position: fixed;
    z-index: 25;
    inset: 0;
    display: block;
    border: 0;
    background: #0009;
  }
  .workspace-main { margin-left: 0; }
  .mobile-menu { display: inline-flex; }
  .workspace-badge { display: none; }
  .topbar { min-height: 66px; }
  .search-box { width: 2.5rem; min-width: 2.5rem; padding: 0 0.65rem; }
  .search-box input,
  .search-box kbd { display: none; }
  .search-box:focus-within { position: absolute; right: 4rem; width: min(65vw, 20rem); background: #172139; }
  .search-box:focus-within input { display: block; }
  .account-label { display: none; }
  .topbar-actions { gap: 0.6rem; }
  .hero-orbit { right: -3rem; bottom: -3rem; opacity: 0.3; }
  .stats-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .complexity-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .interaction-grid { grid-template-columns: 1fr; }
}

@media (max-width: 520px) {
  .auth-card { padding: 1.4rem; }
  .workspace-content { padding-top: 1.2rem; }
  .topbar-title h1 { font-size: 0.85rem; }
  .category-grid,
  .algorithm-grid { grid-template-columns: 1fr; }
  .hero-panel { min-height: 18rem; }
  .hero-panel h2 { font-size: 2rem; }
  .hero-orbit { width: 8rem; height: 8rem; }
  .simulator-panel { padding: 0.9rem; }
  .sim-inputs { align-items: stretch; flex-direction: column; }
  .sim-inputs .primary-button { align-self: flex-start; }
  .detail-hero { flex-direction: column; }
  .favorite-button { align-self: flex-start; }
  .workspace-footer { flex-direction: column; }
}

@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}
```

FE/src/App.tsx
```
import { useEffect, useState } from 'react'
import './App.css'
import AuthForm from './components/AuthForm'
import LearningWorkspace from './components/LearningWorkspace'
import NightSkyCanvas from './components/NightSkyCanvas'
import { useAuth } from './hooks/useAuth'
import type { AuthMode } from './models/auth'
import type { UserProfile } from './models/api'
import { getMe } from './services/contentService'
import { hasSession } from './services/apiClient'

function App() {
  const [mode, setMode] = useState<AuthMode>('login')
  const [user, setUser] = useState<UserProfile | null>(null)
  const [isCheckingSession, setIsCheckingSession] = useState(true)
  const [sessionError, setSessionError] = useState('')
  const { status, isSubmitting, submit, clearStatus } = useAuth()

  useEffect(() => {
    let active = true
    const onExpired = () => {
      if (active) {
        setUser(null)
        setMode('login')
        setSessionError('Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.')
        clearStatus()
      }
    }
    window.addEventListener('algo:session-expired', onExpired)

    if (!hasSession()) {
      setIsCheckingSession(false)
    } else {
      getMe()
        .then((profile) => {
          if (active) setUser(profile)
        })
        .catch((error: unknown) => {
          if (active) {
            setSessionError(
              error instanceof Error ? error.message : 'Không thể khôi phục phiên đăng nhập.',
            )
          }
        })
        .finally(() => {
          if (active) setIsCheckingSession(false)
        })
    }

    return () => {
      active = false
      window.removeEventListener('algo:session-expired', onExpired)
    }
  }, [clearStatus])

  useEffect(() => {
    if (status?.kind !== 'login-success') return
    let active = true
    setIsCheckingSession(true)
    getMe()
      .then((profile) => {
        if (active) {
          setUser(profile)
          setSessionError('')
        }
      })
      .catch((error: unknown) => {
        if (active) {
          setUser({
            ...status.user,
            full_name: null,
            avatar_url: null,
            created_at: '',
          })
          setSessionError(
            error instanceof Error ? error.message : 'Không thể tải hồ sơ tài khoản.',
          )
        }
      })
      .finally(() => {
        if (active) setIsCheckingSession(false)
      })
    return () => {
      active = false
    }
  }, [status])

  function changeMode(nextMode: AuthMode) {
    setMode(nextMode)
    clearStatus()
  }

  function handleLogout(error = '') {
    setUser(null)
    setMode('login')
    setSessionError(error)
    clearStatus()
  }

  if (isCheckingSession) {
    return (
      <main className="session-loading" role="status">
        <span className="loading-spinner" />
        Đang kiểm tra phiên đăng nhập…
      </main>
    )
  }

  if (user) {
    return (
      <LearningWorkspace
        onLogout={async (error) => handleLogout(error)}
        onProfileChange={setUser}
        user={user}
      />
    )
  }

  return (
    <>
      <NightSkyCanvas />
      {sessionError && <p className="session-error" role="alert">{sessionError}</p>}
      <AuthForm
        isSubmitting={isSubmitting}
        mode={mode}
        onModeChange={changeMode}
        onSubmit={submit}
        status={status}
      />
    </>
  )
}

export default App
```

FE/src/index.css
```
:root {
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont,
    "Segoe UI", sans-serif;
  color: #171717;
  font-synthesis: none;
  text-rendering: optimizeLegibility;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;

  font-optical-sizing: auto;
  font-weight: 400;
}

* {
  box-sizing: border-box;
}

body {
  min-width: 320px;
  min-height: 100vh;
  margin: 0;
}

button,
input {
  font-family: inherit;
}

button:focus-visible {
  outline: 2px solid #222;
  outline-offset: 2px;
}
```

FE/src/main.tsx
```
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
```

FE/src/vite-env.d.ts
```
/// <reference types="vite/client" />
```

BE/alembic/versions/20261113_auth_upgrade.py
```
"""Initial Auth migration: upgrade existing users table without deleting data.

Revision ID: 20261113_auth_upgrade
Revises:
"""
from alembic import op
import sqlalchemy as sa

revision = "20261113_auth_upgrade"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    tables = sa.inspect(bind).get_table_names()
    if "users" not in tables:
        op.create_table(
            "users",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("username", sa.String(50), nullable=False, unique=True),
            sa.Column("hashPassword", sa.String(255), nullable=False),
            sa.Column("email", sa.String(100), nullable=False, unique=True),
            sa.Column("role", sa.String(10), nullable=False, server_default="USER"),
            sa.Column("fullName", sa.String(100), nullable=True),
            sa.Column("avatarUrl", sa.String(500), nullable=True),
            sa.Column("createdAt", sa.DateTime(), nullable=False,
                      server_default=sa.text("CURRENT_TIMESTAMP")),
        )
    else:
        cols = {c["name"] for c in sa.inspect(bind).get_columns("users")}
        # Check BEFORE converting existing addresses to lowercase.
        clash = bind.execute(sa.text(
            "SELECT lower(email), count(*) FROM users GROUP BY lower(email) "
            "HAVING count(*) > 1 LIMIT 1"
        )).first()
        if clash:
            raise RuntimeError(
                "Có email trùng nhau khi bỏ phân biệt hoa/thường. "
                "Hãy xử lý dữ liệu trước khi migration."
            )
        bind.execute(sa.text("UPDATE users SET email = lower(trim(email))"))
        # Add nullable first to avoid SQLite non-constant DEFAULT restriction.
        if "role" not in cols:
            op.add_column("users", sa.Column("role", sa.String(10), nullable=True))
        if "fullName" not in cols:
            op.add_column("users", sa.Column("fullName", sa.String(100), nullable=True))
        if "avatarUrl" not in cols:
            op.add_column("users", sa.Column("avatarUrl", sa.String(500), nullable=True))
        if "createdAt" not in cols:
            op.add_column("users", sa.Column("createdAt", sa.DateTime(), nullable=True))
        bind.execute(sa.text("UPDATE users SET role = 'USER' WHERE role IS NULL"))
        bind.execute(sa.text(
            "UPDATE users SET createdAt = CURRENT_TIMESTAMP WHERE createdAt IS NULL"
        ))
        # Batch mode recreates SQLite table preserving rows and existing UNIQUEs.
        with op.batch_alter_table("users", recreate="always") as batch:
            batch.alter_column("role", existing_type=sa.String(10), nullable=False,
                               server_default="USER")
            batch.alter_column("createdAt", existing_type=sa.DateTime(),
                               nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"))

    # If create_all ran before Alembic, these new tables may already exist.
    existing = set(sa.inspect(bind).get_table_names())
    if "refresh_tokens" not in existing:
        op.create_table(
            "refresh_tokens",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
            sa.Column("family_id", sa.String(36), nullable=False),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("revoked_at", sa.DateTime(), nullable=True),
            sa.Column("replaced_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])
        op.create_index("ix_refresh_tokens_family_id", "refresh_tokens", ["family_id"])
    if "password_reset_tokens" not in existing:
        op.create_table(
            "password_reset_tokens",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("used_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_password_reset_tokens_user_id", "password_reset_tokens", ["user_id"])


def downgrade():
    op.drop_index("ix_password_reset_tokens_user_id", table_name="password_reset_tokens")
    op.drop_table("password_reset_tokens")
    op.drop_index("ix_refresh_tokens_family_id", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_user_id", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")
    with op.batch_alter_table("users", recreate="always") as batch:
        batch.drop_column("createdAt")
        batch.drop_column("avatarUrl")
        batch.drop_column("fullName")
        batch.drop_column("role")
```

BE/alembic/versions/20261116_content_modules.py
```
"""Create content, interaction, search and optional learning tables.
Revision ID: 20261116_content_modules
Revises: 20261113_auth_upgrade

SAFE for existing Auth databases. No existing columns are dropped or changed.
"""
from alembic import op
from Models.Base import Base
from Models.Algorithms import (Category,Algorithm,CodeSample,Tag,AlgorithmTag,
                               AlgorithmExample,AlgorithmDiagram,VisualizationConfig,HomeBanner)
from Models.Interaction import Comment,Rating,Favorite,LearningProgress
from Models.Users import User
from Models.AuthToken import RefreshToken,PasswordResetToken

revision='20261116_content_modules'
down_revision='20261113_auth_upgrade'
branch_labels=None
depends_on=None

TABLES=[Category.__table__,Algorithm.__table__,CodeSample.__table__,Tag.__table__,AlgorithmTag.__table__,
        AlgorithmExample.__table__,AlgorithmDiagram.__table__,VisualizationConfig.__table__,HomeBanner.__table__,
        Comment.__table__,Rating.__table__,Favorite.__table__,LearningProgress.__table__]


def upgrade():
    # Allows existing local DBs whose new tables were created by create_all.
    Base.metadata.create_all(bind=op.get_bind(),tables=TABLES,checkfirst=True)


def downgrade():
    # DESTRUCTIVE: only use on disposable test databases.
    Base.metadata.drop_all(bind=op.get_bind(),tables=TABLES,checkfirst=True)
```

FE/src/components/AlgorithmDetail.tsx
```
import { useEffect, useState, type FormEvent } from 'react'
import type { AlgorithmDetail as AlgorithmData, Comment, Rating } from '../models/api'
import {
  addComment,
  getComments,
  getRating,
  setRating,
  updateProgress,
} from '../services/contentService'
import { ApiError } from '../services/apiClient'
import AlgorithmSimulator from './AlgorithmSimulator'

type Props = {
  algorithm: AlgorithmData
  isFavorite: boolean
  onFavorite: () => void
}

function messageFrom(error: unknown): string {
  if (error instanceof ApiError) return error.message
  if (error instanceof TypeError) return 'Không thể kết nối máy chủ.'
  return error instanceof Error ? error.message : 'Đã xảy ra lỗi.'
}

function humanDate(value: string): string {
  return new Intl.DateTimeFormat('vi-VN', { dateStyle: 'medium' }).format(new Date(value))
}

export default function AlgorithmDetail({ algorithm, isFavorite, onFavorite }: Props) {
  const [comments, setComments] = useState<Comment[]>([])
  const [rating, setRatingData] = useState<Rating | null>(null)
  const [commentText, setCommentText] = useState('')
  const [commentBusy, setCommentBusy] = useState(false)
  const [ratingBusy, setRatingBusy] = useState(false)
  const [notice, setNotice] = useState('')
  const [tab, setTab] = useState<'overview' | 'code' | 'pseudocode'>('overview')

  useEffect(() => {
    let active = true
    getComments(algorithm.id)
      .then((result) => { if (active) setComments(result.data) })
      .catch((error: unknown) => { if (active) setNotice(messageFrom(error)) })
    getRating(algorithm.id)
      .then((result) => { if (active) setRatingData(result) })
      .catch((error: unknown) => { if (active) setNotice(messageFrom(error)) })
    return () => { active = false }
  }, [algorithm.id])

  async function submitComment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const content = commentText.trim()
    if (!content) return
    setCommentBusy(true)
    setNotice('')
    try {
      const created = await addComment(algorithm.id, content)
      setComments((previous) => [created, ...previous])
      setCommentText('')
    } catch (error) {
      setNotice(messageFrom(error))
    } finally {
      setCommentBusy(false)
    }
  }

  async function submitRating(score: number) {
    setRatingBusy(true)
    setNotice('')
    try {
      setRatingData(await setRating(algorithm.id, score))
    } catch (error) {
      setNotice(messageFrom(error))
    } finally {
      setRatingBusy(false)
    }
  }

  async function markComplete() {
    setNotice('')
    try {
      await updateProgress(algorithm.id, 'COMPLETED', 100)
      setNotice('Đã ghi nhận hoàn thành thuật toán.')
    } catch (error) {
      setNotice(messageFrom(error))
    }
  }

  return (
    <div className="page-enter algorithm-detail">
      <a className="back-link" href="/algorithms">← Quay lại thư viện</a>
      <section className="detail-hero">
        <div>
          <div className="eyebrow">{algorithm.category.toUpperCase()} <span>•</span> {algorithm.slug}</div>
          <h2>{algorithm.name}</h2>
          <p>{algorithm.summary}</p>
          <div className="detail-meta">
            <span className={`difficulty difficulty-${algorithm.difficulty.toLowerCase()}`}>{algorithm.difficulty}</span>
            <span>{algorithm.avg_rating.toFixed(1)} ★ ({algorithm.rating_count} đánh giá)</span>
            <span>{algorithm.comment_count} bình luận</span>
          </div>
        </div>
        <button className={`favorite-button${isFavorite ? ' is-favorite' : ''}`} onClick={onFavorite}>
          {isFavorite ? '★ Đã lưu' : '☆ Lưu yêu thích'}
        </button>
      </section>

      {notice && <p className="inline-notice" role="status">{notice}</p>}

      {algorithm.has_simulation && <AlgorithmSimulator algorithm={algorithm} />}

      <section className="complexity-grid" aria-label="Độ phức tạp">
        <div><small>Thời gian tốt nhất</small><strong>{algorithm.complexity.time_best}</strong></div>
        <div><small>Thời gian trung bình</small><strong>{algorithm.complexity.time_average}</strong></div>
        <div><small>Thời gian xấu nhất</small><strong>{algorithm.complexity.time_worst}</strong></div>
        <div><small>Bộ nhớ</small><strong>{algorithm.complexity.space}</strong></div>
      </section>

      <div className="detail-tabs" role="tablist" aria-label="Nội dung thuật toán">
        <button aria-selected={tab === 'overview'} onClick={() => setTab('overview')} role="tab">Tổng quan</button>
        <button aria-selected={tab === 'pseudocode'} onClick={() => setTab('pseudocode')} role="tab">Mã giả</button>
        <button aria-selected={tab === 'code'} onClick={() => setTab('code')} role="tab">Mã nguồn</button>
      </div>
      <section className="content-panel detail-content">
        {tab === 'overview' && (
          <>
            <h3>Lý thuyết</h3>
            <p className="prose-text">{algorithm.theory}</p>
            {algorithm.tags.length > 0 && <div className="tag-row">{algorithm.tags.map((tag) => <span key={tag.id}>{tag.name}</span>)}</div>}
            {algorithm.examples.map((example) => (
              <article className="example-card" key={example.id}>
                <h4>{example.title}</h4>
                <p>{example.explanation}</p>
                <div className="example-values"><span>Đầu vào <code>{example.input_data}</code></span><span>Kết quả <code>{example.expected_output}</code></span></div>
              </article>
            ))}
            <button className="secondary-button" onClick={() => void markComplete()}>Đánh dấu đã hoàn thành</button>
          </>
        )}
        {tab === 'pseudocode' && <><h3>Mã giả</h3><pre className="code-block"><code>{algorithm.pseudocode}</code></pre></>}
        {tab === 'code' && (
          <>
            <h3>Mã nguồn tham khảo</h3>
            {algorithm.code_samples.length ? algorithm.code_samples.map((sample) => (
              <article className="sample-code" key={sample.id}><div>{sample.language}</div><pre className="code-block"><code>{sample.code}</code></pre></article>
            )) : <p className="empty-state">Chưa có mã nguồn tham khảo.</p>}
          </>
        )}
      </section>

      <section className="interaction-grid">
        <div className="content-panel rating-panel">
          <div className="section-heading"><div><h3>Đánh giá của bạn</h3><p>{rating ? `${rating.avg_rating.toFixed(1)} / 5 · ${rating.rating_count} lượt đánh giá` : 'Đang tải đánh giá…'}</p></div></div>
          <div className="rating-stars" aria-label="Chọn số sao">
            {[1, 2, 3, 4, 5].map((score) => (
              <button aria-label={`${score} sao`} aria-pressed={rating?.my_score === score} className={rating && rating.my_score !== null && score <= rating.my_score ? 'star-selected' : ''} disabled={ratingBusy} key={score} onClick={() => void submitRating(score)}>★</button>
            ))}
          </div>
          {rating && <div className="rating-distribution">{[5, 4, 3, 2, 1].map((score) => <span key={score}>{score}★ {rating.distribution[String(score)] ?? 0}</span>)}</div>}
        </div>
        <div className="content-panel comments-panel">
          <div className="section-heading"><div><h3>Bình luận</h3><p>Chia sẻ câu hỏi hoặc điều bạn vừa khám phá.</p></div></div>
          <form className="comment-form" onSubmit={(event) => void submitComment(event)}>
            <textarea maxLength={1000} onChange={(event) => setCommentText(event.target.value)} placeholder="Viết bình luận…" required value={commentText} />
            <div><small>{commentText.length}/1000</small><button className="primary-button" disabled={commentBusy || !commentText.trim()} type="submit">{commentBusy ? 'Đang gửi…' : 'Gửi bình luận'}</button></div>
          </form>
          <div className="comment-list">
            {comments.map((comment) => (
              <article className="comment-item" key={comment.id}>
                <span className="avatar">{comment.author.username.slice(0, 1).toUpperCase()}</span>
                <div><div className="comment-heading"><strong>{comment.author.username}</strong><time dateTime={comment.created_at}>{humanDate(comment.created_at)}</time></div><p>{comment.content}</p>{comment.reply_count > 0 && <small>{comment.reply_count} phản hồi</small>}</div>
              </article>
            ))}
            {!comments.length && <p className="empty-state">Chưa có bình luận. Hãy bắt đầu cuộc trò chuyện!</p>}
          </div>
        </div>
      </section>
    </div>
  )
}
```

FE/src/components/AlgorithmSimulator.tsx
```
import { useEffect, useMemo, useState } from 'react'
import type { AlgorithmDetail } from '../models/api'

type Frame = {
  values: number[]
  active: number[]
  sorted: number[]
  message: string
  visited?: number[]
}

type Simulation = {
  kind: 'array' | 'graph' | 'unsupported'
  frames: Frame[]
}

const initialValues = [64, 34, 25, 78, 12, 92, 45, 56, 18, 83]
const graphEdges: Array<[number, number]> = [
  [0, 1], [0, 2], [1, 3], [1, 4], [2, 4], [2, 5], [3, 4], [4, 5],
]

function arraySimulation(slug: string, input: number[], target: number): Simulation {
  const values = [...input]
  const frames: Frame[] = [{ values: [...values], active: [], sorted: [], message: 'Dữ liệu ban đầu.' }]
  const sorted: number[] = []
  const record = (active: number[], message: string) => {
    frames.push({ values: [...values], active, sorted: [...sorted], message })
  }

  if (slug === 'bubble-sort') {
    for (let end = values.length - 1; end > 0; end -= 1) {
      let swapped = false
      for (let index = 0; index < end; index += 1) {
        record([index, index + 1], `So sánh ${values[index]} và ${values[index + 1]}.`)
        if (values[index] > values[index + 1]) {
          ;[values[index], values[index + 1]] = [values[index + 1], values[index]]
          swapped = true
          record([index, index + 1], 'Hoán đổi hai phần tử chưa đúng thứ tự.')
        }
      }
      sorted.unshift(end)
      if (!swapped) break
    }
    sorted.splice(0, sorted.length, ...values.map((_, index) => index))
    record([], 'Sắp xếp hoàn tất.')
  } else if (slug === 'selection-sort') {
    for (let start = 0; start < values.length - 1; start += 1) {
      let minimum = start
      for (let index = start + 1; index < values.length; index += 1) {
        record([minimum, index], `Tìm phần tử nhỏ nhất từ vị trí ${start}.`)
        if (values[index] < values[minimum]) minimum = index
      }
      ;[values[start], values[minimum]] = [values[minimum], values[start]]
      sorted.push(start)
      record([start, minimum], `Đưa ${values[start]} về vị trí ${start}.`)
    }
    sorted.splice(0, sorted.length, ...values.map((_, index) => index))
    record([], 'Sắp xếp hoàn tất.')
  } else if (slug === 'insertion-sort') {
    for (let index = 1; index < values.length; index += 1) {
      let current = index
      while (current > 0 && values[current - 1] > values[current]) {
        record([current - 1, current], 'So sánh phần tử hiện tại với phần đã sắp xếp.')
        ;[values[current - 1], values[current]] = [values[current], values[current - 1]]
        current -= 1
        record([current], 'Chèn phần tử vào đúng vị trí.')
      }
      sorted.splice(0, sorted.length, ...Array.from({ length: index + 1 }, (_, item) => item))
    }
    sorted.splice(0, sorted.length, ...values.map((_, index) => index))
    record([], 'Sắp xếp hoàn tất.')
  } else if (slug === 'merge-sort') {
    const mergeSort = (left: number, right: number) => {
      if (right - left < 2) return
      const middle = Math.floor((left + right) / 2)
      mergeSort(left, middle)
      mergeSort(middle, right)
      const merged: number[] = []
      let a = left
      let b = middle
      while (a < middle && b < right) {
        record([a, b], 'So sánh đầu hai nửa để trộn.')
        if (values[a] <= values[b]) merged.push(values[a++])
        else merged.push(values[b++])
      }
      merged.push(...values.slice(a, middle), ...values.slice(b, right))
      merged.forEach((value, offset) => { values[left + offset] = value })
      record(Array.from({ length: right - left }, (_, offset) => left + offset), 'Gộp hai nửa đã sắp xếp.')
    }
    mergeSort(0, values.length)
    sorted.splice(0, sorted.length, ...values.map((_, index) => index))
    record([], 'Sắp xếp hoàn tất.')
  } else if (slug === 'quick-sort') {
    const quickSort = (left: number, right: number) => {
      if (left >= right) return
      const pivot = values[right]
      let wall = left
      for (let index = left; index < right; index += 1) {
        record([index, right], `So sánh ${values[index]} với pivot ${pivot}.`)
        if (values[index] <= pivot) {
          ;[values[wall], values[index]] = [values[index], values[wall]]
          wall += 1
        }
      }
      ;[values[wall], values[right]] = [values[right], values[wall]]
      sorted.push(wall)
      record([wall], 'Đặt pivot vào vị trí chính xác.')
      quickSort(left, wall - 1)
      quickSort(wall + 1, right)
    }
    quickSort(0, values.length - 1)
    sorted.splice(0, sorted.length, ...values.map((_, index) => index))
    record([], 'Sắp xếp hoàn tất.')
  } else if (slug === 'linear-search') {
    let found = false
    for (let index = 0; index < values.length; index += 1) {
      record([index], `Kiểm tra giá trị ${values[index]}.`)
      if (values[index] === target) {
        sorted.push(index)
        record([index], `Tìm thấy ${target} ở vị trí ${index}.`)
        found = true
        break
      }
    }
    if (!found) record([], `Không tìm thấy ${target} trong mảng.`)
  } else if (slug === 'binary-search') {
    values.sort((a, b) => a - b)
    let left = 0
    let right = values.length - 1
    let found = false
    while (left <= right) {
      const middle = Math.floor((left + right) / 2)
      record([middle], `So sánh ${target} với phần tử giữa ${values[middle]}.`)
      if (values[middle] === target) {
        sorted.push(middle)
        record([middle], `Tìm thấy ${target} ở vị trí ${middle}.`)
        found = true
        break
      }
      if (values[middle] < target) left = middle + 1
      else right = middle - 1
    }
    if (!found) record([], `Không tìm thấy ${target} trong mảng.`)
  } else {
    return { kind: 'unsupported', frames: [] }
  }
  return { kind: 'array', frames }
}

function graphSimulation(slug: string): Simulation {
  if (slug !== 'bfs' && slug !== 'dfs') return { kind: 'unsupported', frames: [] }
  const adjacency = Array.from({ length: 6 }, () => [] as number[])
  graphEdges.forEach(([from, to]) => {
    adjacency[from].push(to)
    adjacency[to].push(from)
  })
  const frames: Frame[] = [{
    values: [], active: [0], sorted: [], visited: [], message: 'Bắt đầu từ đỉnh A.',
  }]
  const visited = new Set<number>([0])
  const pending = [0]
  const order: number[] = []
  while (pending.length) {
    const node = slug === 'bfs' ? pending.shift()! : pending.pop()!
    order.push(node)
    frames.push({
      values: [], active: [node], sorted: [...order], visited: [...visited],
      message: `Đang thăm đỉnh ${String.fromCharCode(65 + node)}.`,
    })
    const neighbors = slug === 'dfs' ? [...adjacency[node]].reverse() : adjacency[node]
    neighbors.forEach((neighbor) => {
      if (!visited.has(neighbor)) {
        visited.add(neighbor)
        pending.push(neighbor)
      }
    })
    frames.push({
      values: [], active: [], sorted: [...order], visited: [...visited],
      message: `Đã xếp các đỉnh chưa thăm vào ${slug === 'bfs' ? 'hàng đợi' : 'ngăn xếp'}.`,
    })
  }
  return { kind: 'graph', frames }
}

function createSimulation(algorithm: AlgorithmDetail, input: number[], target: number): Simulation {
  if (algorithm.slug === 'bfs' || algorithm.slug === 'dfs' || algorithm.slug === 'dijkstra') {
    return graphSimulation(algorithm.slug)
  }
  return arraySimulation(algorithm.slug, input, target)
}

function Bars({ frame }: { frame: Frame }) {
  const max = Math.max(...frame.values, 1)
  return (
    <div className="sim-bars" aria-label={`Mảng: ${frame.values.join(', ')}`}>
      {frame.values.map((value, index) => (
        <div className="sim-bar-column" key={`${index}-${value}`}>
          <span className="sim-value">{value}</span>
          <div
            className={`sim-bar${frame.sorted.includes(index) ? ' sim-bar-sorted' : frame.active.includes(index) ? ' sim-bar-active' : ''}`}
            style={{ height: `${Math.max(8, value / max * 82)}%` }}
          />
          <small>{index}</small>
        </div>
      ))}
    </div>
  )
}

function Graph({ frame }: { frame: Frame }) {
  return (
    <div className="sim-graph">
      {graphEdges.map(([from, to]) => <span className="graph-edge" key={`${from}-${to}`} />)}
      {Array.from({ length: 6 }, (_, index) => (
        <span className={`graph-node${frame.active.includes(index) ? ' graph-node-active' : frame.visited?.includes(index) ? ' graph-node-visited' : ''}`} key={index}>
          {String.fromCharCode(65 + index)}
        </span>
      ))}
    </div>
  )
}

export default function AlgorithmSimulator({ algorithm }: { algorithm: AlgorithmDetail }) {
  const [valuesText, setValuesText] = useState(initialValues.join(', '))
  const [targetText, setTargetText] = useState('45')
  const [simulation, setSimulation] = useState<Simulation | null>(null)
  const [step, setStep] = useState(0)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState('')
  const frame = simulation?.frames[step]
  const canSearch = algorithm.slug.includes('search')
  const allowedSlugs = useMemo(
    () => new Set(['bubble-sort', 'selection-sort', 'insertion-sort', 'merge-sort', 'quick-sort', 'linear-search', 'binary-search', 'bfs', 'dfs']),
    [],
  )

  useEffect(() => {
    setSimulation(null)
    setStep(0)
    setRunning(false)
  }, [algorithm.id])

  useEffect(() => {
    if (!running || !simulation) return
    const timer = window.setInterval(() => {
      setStep((current) => {
        if (current >= simulation.frames.length - 1) {
          setRunning(false)
          return current
        }
        return current + 1
      })
    }, 500)
    return () => window.clearInterval(timer)
  }, [running, simulation])

  function run() {
    const parsed = valuesText.split(',').map((item) => Number(item.trim()))
    if (parsed.length < 2 || parsed.length > 20 || parsed.some((value) => !Number.isFinite(value))) {
      setError('Nhập từ 2 đến 20 số, phân tách bằng dấu phẩy.')
      return
    }
    const target = Number(targetText)
    if (canSearch && !Number.isFinite(target)) {
      setError('Giá trị cần tìm phải là một số hợp lệ.')
      return
    }
    const result = createSimulation(algorithm, parsed, target)
    setSimulation(result)
    setStep(0)
    setRunning(false)
    setError('')
  }

  if (!allowedSlugs.has(algorithm.slug)) {
    return (
      <section className="simulator-panel">
        <div className="section-heading"><div><h3>Mô phỏng từng bước</h3><p>Mô phỏng được đánh dấu cho nội dung này nhưng chưa có bộ trực quan hóa tương ứng ở giao diện.</p></div></div>
      </section>
    )
  }

  return (
    <section className="simulator-panel">
      <div className="section-heading"><div><h3>Mô phỏng tương tác</h3><p>Điều khiển từng bước và quan sát thuật toán xử lý dữ liệu ngay trên trình duyệt.</p></div><span className="sim-local-badge">Xử lý tại trình duyệt</span></div>
      <div className="sim-inputs">
        <label>Dữ liệu đầu vào<input aria-label="Mảng số" onChange={(event) => setValuesText(event.target.value)} value={valuesText} /></label>
        {canSearch && <label>Giá trị cần tìm<input aria-label="Giá trị cần tìm" onChange={(event) => setTargetText(event.target.value)} type="number" value={targetText} /></label>}
        <button className="primary-button" onClick={run}>Tạo mô phỏng</button>
      </div>
      {error && <p className="sim-error" role="alert">{error}</p>}
      {simulation?.kind === 'unsupported' && <p className="sim-error">Chưa có mô phỏng phù hợp cho thuật toán này.</p>}
      {frame && simulation?.kind !== 'unsupported' && (
        <>
          <div className="sim-stage">
            {simulation?.kind === 'graph' ? <Graph frame={frame} /> : <Bars frame={frame} />}
          </div>
          <p className="sim-description" aria-live="polite">{frame.message}</p>
          <div className="sim-controls">
            <button disabled={step === 0} onClick={() => { setRunning(false); setStep(0) }}>⏮</button>
            <button disabled={step === 0} onClick={() => { setRunning(false); setStep((current) => Math.max(0, current - 1)) }}>←</button>
            <button className="primary-button" onClick={() => setRunning((value) => !value)}>{running ? 'Tạm dừng' : step >= (simulation?.frames.length ?? 1) - 1 ? 'Phát lại' : 'Tiếp tục'}</button>
            <button disabled={step >= (simulation?.frames.length ?? 1) - 1} onClick={() => { setRunning(false); setStep((current) => Math.min((simulation?.frames.length ?? 1) - 1, current + 1)) }}>→</button>
            <span>Bước {step + 1} / {simulation?.frames.length ?? 0}</span>
          </div>
        </>
      )}
    </section>
  )
}
```

FE/src/components/AuthForm.tsx
```
import type { FormEvent } from 'react'
import type {
  AuthMode,
  AuthStatus,
  AuthSubmission,
} from '../models/auth'
import LoginFields from './LoginFields'
import RegisterFields from './RegisterFields'

type AuthFormProps = {
  isSubmitting: boolean
  mode: AuthMode
  onModeChange: (mode: AuthMode) => void
  onSubmit: (submission: AuthSubmission) => Promise<void>
  status: AuthStatus | null
}

function AuthForm({
  isSubmitting,
  mode,
  onModeChange,
  onSubmit,
  status,
}: AuthFormProps) {
  const isRegistering = mode === 'register'

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    const formData = new FormData(event.currentTarget)

    if (mode === 'login') {
      void onSubmit({
        mode: 'login',
        data: {
          login: String(formData.get('login') ?? ''),
          password: String(formData.get('password') ?? ''),
          remember_me: formData.get('remember_me') === 'on',
        },
      })
      return
    }

    void onSubmit({
      mode: 'register',
      data: {
        username: String(formData.get('username') ?? ''),
        password: String(formData.get('password') ?? ''),
        email: String(formData.get('email') ?? ''),
      },
    })
  }

  return (
    <main className="auth-page">
      <section className="auth-card" aria-labelledby="auth-title">
        <header className="auth-header">
          <h1 id="auth-title">
            {isRegistering ? 'Tạo tài khoản mới' : 'Chào mừng!'}
          </h1>
          <p>
            {isRegistering
              ? 'Vui lòng nhập thông tin.'
              : 'Tên đăng nhập hoặc email.'}
          </p>
        </header>

        <div className="auth-tabs" role="group" aria-label="Tùy chọn tài khoản">
          <button
            aria-pressed={!isRegistering}
            className={!isRegistering ? 'auth-tab is-active' : 'auth-tab'}
            disabled={isSubmitting}
            onClick={() => onModeChange('login')}
            type="button"
          >
            Đăng nhập
          </button>
          <button
            aria-pressed={isRegistering}
            className={isRegistering ? 'auth-tab is-active' : 'auth-tab'}
            disabled={isSubmitting}
            onClick={() => onModeChange('register')}
            type="button"
          >
            Đăng ký
          </button>
        </div>

        <form className="auth-form" onSubmit={handleSubmit}>
          {isRegistering ? <RegisterFields /> : <LoginFields />}

          {status?.kind === 'error' && (
            <p className="form-status is-error" role="alert">
              {status.message}
            </p>
          )}

          <button className="submit-button" disabled={isSubmitting} type="submit">
            {isSubmitting
              ? 'Chờ trong giây lát…'
              : isRegistering
                ? 'Đăng ký'
                : 'Đăng nhập'}
          </button>
        </form>

        {status?.kind === 'login-success' && (
          <div className="form-status is-success" role="status">
            <p>{status.message}</p>
            <p>
              Đang đăng nhập với <strong>{status.user.username}</strong> (
              {status.user.email})
            </p>
          </div>
        )}

        {status?.kind === 'register-success' && (
          <div className="form-status is-success" role="status">
            <p>
              Đã tạo tài khoản <strong>{status.user.username}</strong> (
              {status.user.email}).
            </p>
            <button
              className="text-button"
              onClick={() => onModeChange('login')}
              type="button"
            >
              Tiếp tục đăng nhập
            </button>
          </div>
        )}
      </section>
    </main>
  )
}

export default AuthForm
```

FE/src/components/LearningWorkspace.tsx
```
import { useEffect, useMemo, useState, type FormEvent } from 'react'
import type { UserProfile } from '../models/api'
import type {
  AlgorithmDetail as AlgorithmDetailData,
  AlgorithmSummary,
  Category,
  HomeData,
  Page,
} from '../models/api'
import {
  getAlgorithm,
  getAlgorithms,
  getCategories,
  getFavorites,
  getHome,
  getProgress,
  getSuggestions,
  searchAlgorithms,
  updateProfile,
  updateProgress,
} from '../services/contentService'
import {
  ApiError,
  clearSession,
  getStoredRefreshToken,
} from '../services/apiClient'
import { apiRequest } from '../services/apiClient'
import AlgorithmDetail from './AlgorithmDetail'

type Route =
  | { page: 'home' }
  | { page: 'algorithms' }
  | { page: 'search'; query: string }
  | { page: 'favorites' }
  | { page: 'profile' }
  | { page: 'algorithm'; slug: string }
  | { page: 'category'; slug: string }

function resolveRoute(pathname: string, search: string, categories: Category[]): Route {
  const parts = pathname.split('/').filter(Boolean)
  if (parts.length === 0) return { page: 'home' }
  if (parts[0] === 'algorithm' && parts[1]) {
    return { page: 'algorithm', slug: decodeURIComponent(parts[1]) }
  }
  if (parts[0] === 'algorithms') {
    return parts[1]
      ? { page: 'algorithm', slug: decodeURIComponent(parts[1]) }
      : { page: 'algorithms' }
  }
  if (parts[0] === 'search') {
    return { page: 'search', query: new URLSearchParams(search).get('q') ?? '' }
  }
  if (parts[0] === 'favorites') return { page: 'favorites' }
  if (parts[0] === 'profile') return { page: 'profile' }
  const category = categories.find((item) => item.slug === parts[0])
  if (category) return { page: 'category', slug: category.slug }
  return { page: 'home' }
}

function difficultyLabel(difficulty: AlgorithmSummary['difficulty']): string {
  return { EASY: 'Dễ', MEDIUM: 'Trung bình', HARD: 'Nâng cao' }[difficulty]
}

function messageFrom(error: unknown): string {
  if (error instanceof ApiError) return error.message
  if (error instanceof TypeError) {
    return 'Không thể kết nối máy chủ. Hãy kiểm tra backend đang chạy rồi thử lại.'
  }
  return error instanceof Error ? error.message : 'Đã xảy ra lỗi. Vui lòng thử lại.'
}

function AlgorithmCard({ item }: { item: AlgorithmSummary }) {
  return (
    <article className="algorithm-card">
      <div className="algorithm-card-top">
        <span className="category-chip">{item.category}</span>
        <span className={`difficulty difficulty-${item.difficulty.toLowerCase()}`}>
          {difficultyLabel(item.difficulty)}
        </span>
      </div>
      <h3>{item.name}</h3>
      <p>{item.summary}</p>
      <div className="algorithm-card-meta">
        <span>{item.avg_rating.toFixed(1)} ★</span>
        <span>{item.rating_count} đánh giá</span>
        {item.has_simulation && <span>Mô phỏng</span>}
      </div>
      <a className="card-link" href={`/algorithm/${encodeURIComponent(item.slug)}`}>
        Khám phá thuật toán <span aria-hidden="true">→</span>
      </a>
    </article>
  )
}

function AlgorithmGrid({ items }: { items: AlgorithmSummary[] }) {
  if (!items.length) {
    return <p className="empty-state">Chưa có thuật toán phù hợp.</p>
  }
  return (
    <div className="algorithm-grid">
      {items.map((item) => (
        <AlgorithmCard item={item} key={item.id} />
      ))}
    </div>
  )
}

function LoadingState() {
  return (
    <div className="loading-state" role="status">
      <span className="loading-spinner" />
      Đang tải dữ liệu…
    </div>
  )
}

function SearchBox() {
  const [query, setQuery] = useState('')
  const [suggestions, setSuggestions] = useState<Array<{ slug: string; name: string }>>([])
  const [open, setOpen] = useState(false)

  useEffect(() => {
    const trimmed = query.trim()
    if (trimmed.length < 1) {
      setSuggestions([])
      return
    }
    let active = true
    const timeout = window.setTimeout(() => {
      getSuggestions(trimmed)
        .then((items) => {
          if (active) setSuggestions(items)
        })
        .catch(() => {
          if (active) setSuggestions([])
        })
    }, 250)
    return () => {
      active = false
      window.clearTimeout(timeout)
    }
  }, [query])

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (query.trim()) {
      window.location.href = `/search?q=${encodeURIComponent(query.trim())}`
    }
  }

  return (
    <form className="search-box" onSubmit={submit} role="search">
      <span aria-hidden="true" className="search-icon">
        ⌕
      </span>
      <input
        aria-label="Tìm thuật toán"
        autoComplete="off"
        onBlur={() => window.setTimeout(() => setOpen(false), 120)}
        onChange={(event) => setQuery(event.target.value)}
        onFocus={() => setOpen(true)}
        placeholder="Tìm kiếm thuật toán…"
        value={query}
      />
      <kbd>⌘ K</kbd>
      {open && suggestions.length > 0 && (
        <div className="suggestion-menu">
          {suggestions.map((item) => (
            <a href={`/algorithm/${encodeURIComponent(item.slug)}`} key={item.slug}>
              {item.name}
              <span aria-hidden="true">↗</span>
            </a>
          ))}
          {query.trim() && (
            <button type="submit">Xem tất cả kết quả cho “{query.trim()}”</button>
          )}
        </div>
      )}
    </form>
  )
}

function HomePage({ data }: { data: HomeData }) {
  return (
    <div className="page-enter">
      <section className="hero-panel">
        <div className="eyebrow"><span /> SẴN SÀNG CHO MỘT ĐIỀU MỚI?</div>
        <h2>{data.intro.title}</h2>
        <p>{data.intro.description}</p>
        <div className="hero-actions">
          <a className="primary-button" href="/algorithms">Bắt đầu học ngay <span>→</span></a>
          <a className="quiet-link" href="/favorites">Xem danh sách yêu thích</a>
        </div>
        <div aria-hidden="true" className="hero-orbit">
          <span>O(n log n)</span><i /><b /><em />
        </div>
      </section>
      <section className="stats-grid" aria-label="Thống kê">
        <div className="stat-card"><strong>{data.stats.algorithms}</strong><span>Thuật toán</span><small>Kiến thức từ cơ bản đến nâng cao</small></div>
        <div className="stat-card"><strong>{data.categories.length}</strong><span>Danh mục</span><small>Khám phá nhiều chủ đề</small></div>
        <div className="stat-card"><strong>{data.stats.users}</strong><span>Người học</span><small>Cùng học và chia sẻ kiến thức</small></div>
        <div className="stat-card"><strong>{data.featured_algorithms.length}</strong><span>Nổi bật</span><small>Được cộng đồng quan tâm</small></div>
      </section>
      {data.banners.length > 0 && (
        <section className="banner-strip" aria-label="Thông tin nổi bật">
          {data.banners.map((banner) => (
            <a href={banner.link_url} key={banner.id}>
              <span>{banner.title}</span><span aria-hidden="true">↗</span>
            </a>
          ))}
        </section>
      )}
      <section className="workspace-section">
        <div className="section-heading">
          <div><h2>Chọn một chủ đề để khám phá</h2><p>Bắt đầu từ danh mục phù hợp với hành trình của bạn.</p></div>
          <a href="/algorithms">Tất cả thuật toán →</a>
        </div>
        <div className="category-grid">
          {data.categories.map((category, index) => (
            <a className={`category-card category-card-${index % 4}`} href={`/${encodeURIComponent(category.slug)}`} key={category.id}>
              <span className="category-symbol">{['↗', '⌕', '⌘', '◈'][index % 4]}</span>
              <h3>{category.name}</h3>
              <p>{category.description ?? 'Khám phá các thuật toán trong danh mục này.'}</p>
              <small>{category.algorithm_count ?? 0} thuật toán <span>→</span></small>
            </a>
          ))}
        </div>
      </section>
      <section className="workspace-section">
        <div className="section-heading">
          <div><h2>Thuật toán nổi bật</h2><p>Khám phá các nội dung đang được quan tâm.</p></div>
          <a href="/algorithms">Xem thư viện →</a>
        </div>
        <AlgorithmGrid items={data.featured_algorithms} />
      </section>
    </div>
  )
}

function ProfilePage({
  user,
  onProfileChange,
}: {
  user: UserProfile
  onProfileChange: (user: UserProfile) => void
}) {
  const [name, setName] = useState(user.full_name ?? '')
  const [notice, setNotice] = useState('')
  const [saving, setSaving] = useState(false)

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSaving(true)
    setNotice('')
    try {
      const updated = await updateProfile(name.trim())
      onProfileChange(updated)
      setNotice('Đã cập nhật hồ sơ.')
    } catch (error) {
      setNotice(messageFrom(error))
    } finally {
      setSaving(false)
    }
  }

  return (
    <section className="content-panel profile-panel">
      <div className="section-heading"><div><h2>Hồ sơ cá nhân</h2><p>Thông tin tài khoản AlgoVisual của bạn.</p></div></div>
      <div className="profile-identity">
        <span className="avatar-large">{(user.full_name || user.username).slice(0, 1).toUpperCase()}</span>
        <div><strong>{user.full_name || user.username}</strong><span>{user.role ?? 'USER'}</span></div>
      </div>
      <form className="profile-form" onSubmit={submit}>
        <label>Tên hiển thị<input maxLength={100} onChange={(event) => setName(event.target.value)} value={name} /></label>
        <label>Tên đăng nhập<input readOnly value={user.username} /></label>
        <label>Email<input readOnly value={user.email} /></label>
        <button className="primary-button" disabled={saving} type="submit">{saving ? 'Đang lưu…' : 'Lưu thay đổi'}</button>
      </form>
      {notice && <p className="inline-notice" role="status">{notice}</p>}
    </section>
  )
}

type WorkspaceProps = {
  user: UserProfile
  onLogout: (error?: string) => Promise<void>
  onProfileChange: (user: UserProfile) => void
}

export default function LearningWorkspace({ user, onLogout, onProfileChange }: WorkspaceProps) {
  const [categories, setCategories] = useState<Category[]>([])
  const route = useMemo(
    () => resolveRoute(window.location.pathname, window.location.search, categories),
    [categories],
  )
  const routeSlug = route.page === 'algorithm' || route.page === 'category' ? route.slug : ''
  const routeQuery = route.page === 'search' ? route.query : ''
  const [home, setHome] = useState<HomeData | null>(null)
  const [list, setList] = useState<Page<AlgorithmSummary> | null>(null)
  const [detail, setDetail] = useState<AlgorithmDetailData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [difficulty, setDifficulty] = useState<'' | AlgorithmSummary['difficulty']>('')
  const [sort, setSort] = useState<'name' | 'rating' | 'newest'>('rating')
  const [mobileNav, setMobileNav] = useState(false)
  const [accountMenu, setAccountMenu] = useState(false)
  const [favorites, setFavorites] = useState<Set<string>>(new Set())
  const title =
    route.page === 'home' ? 'Trang chủ' :
    route.page === 'algorithm' ? (detail?.name ?? 'Thuật toán') :
    route.page === 'category' ? (categories.find((item) => item.slug === route.slug)?.name ?? 'Danh mục') :
    route.page === 'profile' ? 'Hồ sơ cá nhân' :
    route.page === 'favorites' ? 'Thuật toán yêu thích' :
    route.page === 'search' ? 'Kết quả tìm kiếm' : 'Thư viện thuật toán'

  useEffect(() => {
    let active = true
    getCategories()
      .then((items) => { if (active) setCategories(items) })
      .catch((cause: unknown) => { if (active) setError(messageFrom(cause)) })
    getFavorites()
      .then((result) => { if (active) setFavorites(new Set(result.data.map((item) => item.slug))) })
      .catch(() => {
        if (active) setFavorites(new Set())
      })
    return () => { active = false }
  }, [])

  useEffect(() => {
    let active = true
    setLoading(true)
    setError('')
    setHome(null)
    setList(null)
    setDetail(null)
    const load = async () => {
      try {
        if (route.page === 'home') {
          const result = await getHome()
          if (active) setHome(result)
        } else if (route.page === 'algorithm') {
          const result = await getAlgorithm(routeSlug)
          if (active) setDetail(result)
        } else if (route.page === 'favorites') {
          const result = await getFavorites()
          if (active) setList(result)
        } else if (route.page === 'search') {
          if (!routeQuery.trim()) {
            if (active) setList({ data: [], meta: { page: 1, page_size: 20, total: 0 } })
          } else {
            const result = await searchAlgorithms(routeQuery)
            if (active) setList(result)
          }
        } else if (route.page === 'profile') {
          if (active) setList(null)
        } else {
          const category = route.page === 'category'
            ? categories.find((item) => item.slug === routeSlug)
            : undefined
          const result = await getAlgorithms({
            categoryId: category?.id,
            difficulty: difficulty || undefined,
            sort,
          })
          if (active) setList(result)
        }
      } catch (cause) {
        if (active) setError(messageFrom(cause))
      } finally {
        if (active) setLoading(false)
      }
    }
    void load()
    return () => { active = false }
  }, [route.page, routeSlug, routeQuery, categories, difficulty, sort])

  useEffect(() => {
    if (!detail) return
    void getProgress(detail.id)
      .then((progress) => {
        if (progress.status === 'NOT_STARTED') {
          return updateProgress(detail.id, 'IN_PROGRESS', 10)
        }
        return undefined
      })
      .catch((cause: unknown) => setError(messageFrom(cause)))
  }, [detail])

  async function toggleFavorite(algorithm: AlgorithmDetailData) {
    const isSaved = favorites.has(algorithm.slug)
    try {
      if (isSaved) {
        await apiRequest<void>(`/algorithms/${algorithm.id}/favorite`, { method: 'DELETE' })
        setFavorites((previous) => {
          const next = new Set(previous)
          next.delete(algorithm.slug)
          return next
        })
      } else {
        await apiRequest(`/algorithms/${algorithm.id}/favorite`, { method: 'POST' })
        setFavorites((previous) => new Set(previous).add(algorithm.slug))
      }
    } catch (cause) {
      setError(messageFrom(cause))
    }
  }

  async function logout() {
    try {
      await apiRequest('/users/me')
      const refreshToken = getStoredRefreshToken()
      if (refreshToken) {
        await apiRequest('/auth/logout', {
          method: 'POST',
          body: JSON.stringify({ refresh_token: refreshToken }),
        })
      }
    } catch (cause) {
      await onLogout(messageFrom(cause))
      clearSession()
      return
    } finally {
      clearSession()
    }
    await onLogout()
  }

  const isLibrary = route.page === 'algorithms' || route.page === 'category'
  const category = route.page === 'category'
    ? categories.find((item) => item.slug === route.slug)
    : undefined

  return (
    <div className="workspace">
      {mobileNav && <button className="mobile-backdrop" onClick={() => setMobileNav(false)} aria-label="Đóng điều hướng" />}
      <aside className={`sidebar${mobileNav ? ' sidebar-open' : ''}`}>
        <a className="brand" href="/">
          <span className="brand-mark">A</span>
          <span>Algo<span>Visual</span></span>
        </a>
        <p className="nav-caption">KHÔNG GIAN HỌC TẬP</p>
        <nav className="side-nav" aria-label="Điều hướng chính">
          <a className={route.page === 'home' ? 'nav-active' : ''} href="/">⌂ <span>Trang chủ</span></a>
          <a className={isLibrary ? 'nav-active' : ''} href="/algorithms">▦ <span>Thư viện thuật toán</span></a>
          {categories.map((item) => (
            <a className={route.page === 'category' && route.slug === item.slug ? 'nav-active nav-child-active' : 'nav-child'} href={`/${encodeURIComponent(item.slug)}`} key={item.id}>
              <span className="nav-dot" /> <span>{item.name}</span>
            </a>
          ))}
          <a className={route.page === 'favorites' ? 'nav-active' : ''} href="/favorites">☆ <span>Yêu thích</span></a>
          <a className={route.page === 'profile' ? 'nav-active' : ''} href="/profile">◉ <span>Hồ sơ cá nhân</span></a>
        </nav>
        <div className="sidebar-bottom">
          <div className="learning-tip"><span>✦</span><strong>Mỗi ngày, một bước tiến</strong><p>Một thuật toán nhỏ hôm nay. Một bước tiến lớn ngày mai.</p><a href="/algorithms">Tiếp tục khám phá →</a></div>
          <div className="sidebar-user"><span className="avatar">{(user.full_name || user.username).slice(0, 1).toUpperCase()}</span><div><strong>{user.full_name || user.username}</strong><small>Người học AlgoVisual</small></div></div>
        </div>
      </aside>
      <div className="workspace-main">
        <header className="topbar">
          <div className="topbar-title">
            <button className="mobile-menu" onClick={() => setMobileNav(true)} aria-label="Mở điều hướng">☰</button>
            <h1>{title}</h1><span className="workspace-badge">Learning workspace</span>
          </div>
          <div className="topbar-actions"><SearchBox />
            <div className="account-wrap">
              <button className="account-button" onClick={() => setAccountMenu((value) => !value)} aria-expanded={accountMenu} aria-label="Tài khoản"><span className="avatar">{(user.full_name || user.username).slice(0, 1).toUpperCase()}</span><span className="account-label">{user.full_name || user.username}</span><span>⌄</span></button>
              {accountMenu && <div className="account-menu"><a href="/profile">Hồ sơ cá nhân</a><button onClick={() => void logout()}>Đăng xuất</button></div>}
            </div>
          </div>
        </header>
        <main className="workspace-content">
          {error && <div className="notice-error" role="alert">{error}<button onClick={() => setError('')} aria-label="Đóng">×</button></div>}
          {loading && <LoadingState />}
          {!loading && route.page === 'home' && home && <HomePage data={home} />}
          {!loading && route.page === 'algorithm' && detail && (
            <AlgorithmDetail
              algorithm={detail}
              isFavorite={favorites.has(detail.slug)}
              onFavorite={() => void toggleFavorite(detail)}
            />
          )}
          {!loading && route.page === 'favorites' && (
            <section className="workspace-section"><div className="section-heading"><div><h2>Đã lưu để học sau</h2><p>{list?.meta.total ?? 0} thuật toán yêu thích</p></div></div><AlgorithmGrid items={list?.data ?? []} /></section>
          )}
          {!loading && (isLibrary || route.page === 'search') && (
            <section className="workspace-section">
              <div className="library-intro"><span className="eyebrow">THƯ VIỆN THUẬT TOÁN</span><h2>{route.page === 'search' ? `Kết quả cho “${route.query}”` : category?.name ?? 'Một thư viện. Vô vàn khám phá.'}</h2><p>{category?.description ?? 'Tìm hiểu lý thuyết, độ phức tạp và mô phỏng từng bước.'}</p></div>
              {route.page !== 'search' && <div className="filter-row">
                <label>Độ khó<select value={difficulty} onChange={(event) => setDifficulty(event.target.value as '' | AlgorithmSummary['difficulty'])}><option value="">Tất cả</option><option value="EASY">Dễ</option><option value="MEDIUM">Trung bình</option><option value="HARD">Nâng cao</option></select></label>
                <label>Sắp xếp<select value={sort} onChange={(event) => setSort(event.target.value as typeof sort)}><option value="rating">Được đánh giá cao</option><option value="name">Tên A–Z</option><option value="newest">Mới nhất</option></select></label>
              </div>}
              <p className="result-count">{list?.meta.total ?? 0} thuật toán</p>
              <AlgorithmGrid items={list?.data ?? []} />
            </section>
          )}
          {!loading && route.page === 'profile' && <ProfilePage user={user} onProfileChange={onProfileChange} />}
        </main>
        <footer className="workspace-footer"><span>© {new Date().getFullYear()} AlgoVisual</span><span>Học thuật toán theo cách của bạn.</span></footer>
      </div>
    </div>
  )
}
```

FE/src/components/LoginFields.tsx
```
function LoginFields() {
  return (
    <>
      <div className="form-field">
        <label htmlFor="login">Tên đăng nhập hoặc email</label>
        <input
          autoComplete="username"
          id="login"
          name="login"
          required
        />
      </div>
      <label className="remember-field">
        <input name="remember_me" type="checkbox" />
        Ghi nhớ đăng nhập trên thiết bị này
      </label>

      <div className="form-field">
        <label htmlFor="login-password">Mật khẩu</label>
        <input
          autoComplete="current-password"
          id="login-password"
          name="password"
          required
          type="password"
        />
      </div>
    </>
  )
}

export default LoginFields
```

FE/src/components/NightSkyCanvas.tsx
```
import { useEffect, useRef } from 'react'

type Particle = {
  sx: number
  sy: number
  sz: number
  th: number
  x: number
  y: number
  vy: number
  sp: number
  len: number
  l: number
  dx: number
  dy: number
  a: number
  b: number
  cap: boolean
}

type Star = {
  x: number
  y: number
  p: number
  s: number
}

function NightSkyCanvas() {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    if (!canvasRef.current) {
      return
    }

    const cv = canvasRef.current
    const context = cv.getContext('2d')
    if (!context) {
      return
    }

    const ctx = context
    let W = 0
    let H = 0
    let dpr: number

    function resize() {
      dpr = Math.min(window.devicePixelRatio || 1, 2)
      W = window.innerWidth
      H = window.innerHeight
      cv.width = W * dpr
      cv.height = H * dpr
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    }

    window.addEventListener('resize', resize)
    resize()

    // ---- Cấu hình (chỉnh ở đây) ----
    const N = W < 700 ? 33 : 60
    const FALL = [70, 260]
    const CHARGE_UP = 0.4
    const CHARGE_DOWN = 0.35
    const ROT = 0.45
    const TILT = 0.38
    const BUCKETS = 5
    const LEN = 4
    const RANGE_K = 0.28

    const ga = Math.PI * (3 - Math.sqrt(5))
    const ps: Particle[] = []

    for (let i = 0; i < N; i++) {
      const y = 1 - (2 * (i + 0.5)) / N
      const r = Math.sqrt(1 - y * y)
      const t = ga * i
      ps.push({
        sx: Math.cos(t) * r,
        sy: y,
        sz: Math.sin(t) * r,
        th: Math.random() * 0.85,
        x: Math.random() * W,
        y: Math.random() * H,
        vy: 0,
        sp: FALL[0] + Math.random() * (FALL[1] - FALL[0]),
        len: (8 + Math.random() * 16) * LEN,
        l: 12 * LEN,
        dx: 0,
        dy: -1,
        a: 0.3 + Math.random() * 0.6,
        b: 0,
        cap: false,
      })
    }

    const stars: Star[] = []
    for (let i = 0; i < 90; i++) {
      stars.push({
        x: Math.random(),
        y: Math.random() * 0.9,
        p: Math.random() * 6.28,
        s: Math.random() * 0.8 + 0.4,
      })
    }

    let mx = W / 2
    let my = H / 2
    let cx = mx
    let cy = my
    let last = -1e9
    let charge = 0
    let prev = performance.now()
    let time = 0
    let animationFrame = 0

    function move(e: PointerEvent) {
      mx = e.clientX
      my = e.clientY
      last = performance.now()
    }

    window.addEventListener('pointermove', move)
    window.addEventListener('pointerdown', move)

    function frame(now: number) {
      const dt = Math.min((now - prev) / 1000, 0.05)
      prev = now
      time += dt
      ctx.clearRect(0, 0, W, H)

      ctx.fillStyle = '#cfe4ff'
      for (let i = 0; i < stars.length; i++) {
        const s = stars[i]
        ctx.globalAlpha =
          0.25 +
          0.35 *
            Math.sin(time * s.s + s.p) *
            Math.sin(time * s.s + s.p)
        ctx.fillRect(s.x * W, s.y * H, 1.2, 1.2)
      }

      const active = now - last < 1500
      charge += (active ? CHARGE_UP : -CHARGE_DOWN) * dt
      charge = Math.max(0, Math.min(1, charge))
      const k = 1 - Math.exp(-6 * dt)
      cx += (mx - cx) * k
      cy += (my - cy) * k

      const R = Math.max(64, Math.min(W, H) * 0.141)
      const RANGE = Math.max(140, Math.min(W, H) * RANGE_K)
      const ang = time * ROT
      const ca = Math.cos(ang)
      const sa = Math.sin(ang)
      const ct = Math.cos(TILT)
      const st = Math.sin(TILT)
      const kd = 1 - Math.exp(-8 * dt)

      for (let i = 0; i < N; i++) {
        const p = ps[i]
        let tdx: number
        let tdy: number
        let tl: number
        let alpha: number

        if (charge <= p.th) p.cap = false
        else if (!p.cap && Math.hypot(p.x - cx, p.y - cy) < RANGE) {
          p.cap = true
        }

        if (p.cap) {
          const x1 = p.sx * ca + p.sz * sa
          const z1 = -p.sx * sa + p.sz * ca
          const y2 = p.sy * ct - z1 * st
          const z2 = p.sy * st + z1 * ct
          const d = (z2 + 1) / 2
          const sc = 0.8 + 0.4 * d
          const tx = cx + x1 * R * sc
          const ty = cy + y2 * R * sc
          const e = 1 - Math.exp(-(2.5 + p.sp / 60) * dt)
          p.x += (tx - p.x) * e
          p.y += (ty - p.y) * e
          p.vy = 0
          const m = Math.hypot(x1, y2) + 1e-4
          tdx = x1 / m
          tdy = y2 / m
          tl = p.len * 0.45 * (0.35 + 0.65 * m) * sc
          alpha = Math.min(1, p.a * 0.35 + 0.25 + 0.55 * d)
        } else {
          p.vy += (p.sp - p.vy) * (1 - Math.exp(-2 * dt))
          p.y += p.vy * dt
          tdx = 0
          tdy = -1
          tl = p.len
          alpha = p.a
          if (p.y - p.len > H) {
            p.y = -p.len - Math.random() * H * 0.3
            p.x = Math.random() * W
          }
        }

        p.dx += (tdx - p.dx) * kd
        p.dy += (tdy - p.dy) * kd
        p.l += (tl - p.l) * kd
        p.b = Math.min(BUCKETS - 1, (alpha * BUCKETS) | 0)
      }

      ctx.lineCap = 'round'
      ctx.lineWidth = 1.4
      for (let b = 0; b < BUCKETS; b++) {
        ctx.globalAlpha = (b + 1) / BUCKETS
        ctx.strokeStyle = `hsl(200,90%,${66 + b * 4}%)`
        ctx.beginPath()
        for (let i = 0; i < N; i++) {
          const q = ps[i]
          if (q.b !== b) continue
          ctx.moveTo(q.x, q.y)
          ctx.lineTo(q.x + q.dx * q.l, q.y + q.dy * q.l)
        }
        ctx.stroke()
      }

      ctx.globalAlpha = 1
      animationFrame = window.requestAnimationFrame(frame)
    }

    animationFrame = window.requestAnimationFrame(frame)

    return () => {
      window.cancelAnimationFrame(animationFrame)
      window.removeEventListener('resize', resize)
      window.removeEventListener('pointermove', move)
      window.removeEventListener('pointerdown', move)
    }
  }, [])

  return <canvas aria-hidden="true" className="night-sky-canvas" ref={canvasRef} />
}

export default NightSkyCanvas
```

FE/src/components/RegisterFields.tsx
```
function RegisterFields() {
  return (
    <>
      <div className="form-field">
        <label htmlFor="username">Tên đăng nhập</label>
        <input
          aria-describedby="username-hint"
          autoComplete="username"
          id="username"
          maxLength={50}
          minLength={3}
          name="username"
          pattern="[A-Za-z0-9_]{3,50}"
          required
          title="Tên đăng nhập gồm 3–50 ký tự: chữ cái không dấu, số hoặc dấu gạch dưới."
        />
        <span className="field-hint" id="username-hint">
          Từ 3–50 ký tự; chỉ dùng chữ cái không dấu, số và dấu gạch dưới.
        </span>
      </div>

      <div className="form-field">
        <label htmlFor="email">Email</label>
        <input
          autoComplete="email"
          id="email"
          maxLength={100}
          name="email"
          pattern="[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}"
          required
          type="email"
        />
      </div>

      <div className="form-field">
        <label htmlFor="register-password">Mật khẩu</label>
        <input
          aria-describedby="password-hint"
          autoComplete="new-password"
          id="register-password"
          maxLength={64}
          minLength={8}
          name="password"
          pattern="(?=.*[A-Z])(?=.*[0-9])(?=.*[^A-Za-z0-9]).{8,64}"
          required
          title="Mật khẩu ít nhất 8 ký tự, có chữ cái in hoa, số và ký tự đặc biệt"
          type="password"
        />
        <span className="field-hint" id="password-hint">
          Mật khẩu ít nhất 8 ký tự, có chữ cái in hoa, số và ký tự đặc biệt
        </span>
      </div>
    </>
  )
}

export default RegisterFields
```

FE/src/hooks/useAuth.ts
```
import { useCallback, useState } from 'react'
import type { AuthStatus, AuthSubmission } from '../models/auth'
import { login, register } from '../services/authService'

function getSubmissionError(error: unknown): string {
  if (error instanceof TypeError) {
    return 'Không thể kết nối máy chủ. Hãy kiểm tra backend đang chạy rồi thử lại.'
  }

  if (error instanceof Error) {
    return error.message
  }

  return 'Đã xảy ra lỗi. Vui lòng thử lại.'
}

export function useAuth() {
  const [status, setStatus] = useState<AuthStatus | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  async function submit(submission: AuthSubmission): Promise<void> {
    setStatus(null)
    setIsSubmitting(true)

    try {
      if (submission.mode === 'login') {
        const response = await login(submission.data)

        setStatus({
          kind: 'login-success',
          message: response.message,
          user: response.user,
        })
      } else {
        const user = await register(submission.data)
        setStatus({ kind: 'register-success', user })
      }
    } catch (error) {
      setStatus({ kind: 'error', message: getSubmissionError(error) })
    } finally {
      setIsSubmitting(false)
    }
  }

  const clearStatus = useCallback(() => {
    setStatus(null)
  }, [])

  return { status, isSubmitting, submit, clearStatus }
}
```

FE/src/models/api.ts
```
import type { User } from './auth'

export type UserProfile = User & {
  full_name: string | null
  avatar_url: string | null
  created_at: string
}

export type PageMeta = {
  page: number
  page_size: number
  total: number
}

export type Page<T> = {
  data: T[]
  meta: PageMeta
}

export type Category = {
  id: number
  name: string
  slug: string
  description: string | null
  algorithm_count: number | null
}

export type AlgorithmSummary = {
  id: number
  slug: string
  name: string
  summary: string
  category: string
  category_id: number
  difficulty: 'EASY' | 'MEDIUM' | 'HARD'
  avg_rating: number
  rating_count: number
  has_simulation: boolean
}

export type AlgorithmDetail = AlgorithmSummary & {
  theory: string
  pseudocode: string
  code_samples: Array<{ id: number; language: string; code: string }>
  complexity: {
    time_best: string
    time_average: string
    time_worst: string
    space: string
  }
  tags: Array<{ id: number; name: string; slug: string }>
  examples: Array<{
    id: number
    title: string
    input_data: string
    expected_output: string
    explanation: string
    sort_order: number
  }>
  diagrams: Array<{
    id: number
    title: string
    diagram_type: string
    source_text: string | null
    image_url: string | null
    sort_order: number
  }>
  visualization_config: { renderer_key: string; config_json: string } | null
  comment_count: number
  created_at: string
  updated_at: string
}

export type HomeData = {
  intro: { title: string; description: string }
  banners: Array<{
    id: number
    title: string
    image_url: string
    link_url: string
    sort_order: number
    is_active: boolean
  }>
  featured_algorithms: AlgorithmSummary[]
  categories: Category[]
  stats: { algorithms: number; users: number }
}

export type Comment = {
  id: number
  content: string
  author: { id: number; username: string; avatar_url: string | null }
  algorithm_id: number
  parent_id: number | null
  reply_count: number
  created_at: string
  updated_at: string
  is_mine: boolean
}

export type Rating = {
  avg_rating: number
  rating_count: number
  my_score: number | null
  distribution: Record<string, number>
}

export type LearningProgress = {
  algorithm_id: number
  status: 'NOT_STARTED' | 'IN_PROGRESS' | 'COMPLETED'
  progress_percent: number
  last_viewed_at: string | null
  completed_at: string | null
}

export type AuthTokens = {
  access_token: string
  refresh_token: string
  expires_in: number
  token_type: string
}
```

FE/src/models/auth.ts
```
export type AuthMode = 'login' | 'register'

export type User = {
  id: number
  username: string
  email: string
  role?: 'USER' | 'ADMIN'
}

export type LoginRequest = {
  login: string
  password: string
  remember_me: boolean
}

export type RegisterRequest = {
  username: string
  password: string
  email: string
}

export type LoginResponse = {
  message: string
  access_token: string
  refresh_token: string
  expires_in: number
  token_type: string
  user: User
}

export type AuthSubmission =
  | { mode: 'login'; data: LoginRequest }
  | { mode: 'register'; data: RegisterRequest }

export type AuthStatus =
  | { kind: 'error'; message: string }
  | { kind: 'login-success'; message: string; user: User }
  | { kind: 'register-success'; user: User }
```

FE/src/services/apiClient.ts
```
import type { AuthTokens } from '../models/api'

const SESSION_KEY = 'algo-web-session'

export class ApiError extends Error {
  readonly status: number

  constructor(
    message: string,
    status: number,
  ) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

type Session = Pick<AuthTokens, 'access_token' | 'refresh_token'>

function readSession(): Session | null {
  try {
    const raw = localStorage.getItem(SESSION_KEY)
    if (!raw) return null
    const value: unknown = JSON.parse(raw)
    if (
      typeof value === 'object' &&
      value !== null &&
      'access_token' in value &&
      'refresh_token' in value &&
      typeof value.access_token === 'string' &&
      typeof value.refresh_token === 'string'
    ) {
      return { access_token: value.access_token, refresh_token: value.refresh_token }
    }
  } catch {
    localStorage.removeItem(SESSION_KEY)
  }
  return null
}

export function saveSession(tokens: Session): void {
  localStorage.setItem(SESSION_KEY, JSON.stringify(tokens))
}

export function clearSession(): void {
  localStorage.removeItem(SESSION_KEY)
}

export function hasSession(): boolean {
  return readSession() !== null
}

export function getStoredRefreshToken(): string | null {
  return readSession()?.refresh_token ?? null
}

function announceExpiredSession(): void {
  clearSession()
  window.dispatchEvent(new CustomEvent('algo:session-expired'))
}

function errorMessage(payload: unknown, status: number): string {
  if (typeof payload === 'object' && payload !== null && 'detail' in payload) {
    const detail = payload.detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) {
      const messages = detail.flatMap((item) =>
        typeof item === 'object' &&
        item !== null &&
        'msg' in item &&
        typeof item.msg === 'string'
          ? [item.msg]
          : [],
      )
      if (messages.length) return messages.join(' ')
    }
  }
  return `Yêu cầu không thành công (mã ${status}). Vui lòng thử lại.`
}

async function readResponse(response: Response): Promise<unknown> {
  if (response.status === 204) return undefined
  const text = await response.text()
  if (!text) return undefined
  try {
    return JSON.parse(text) as unknown
  } catch {
    throw new ApiError('Máy chủ trả về dữ liệu không hợp lệ.', response.status)
  }
}

let refreshInFlight: Promise<string | null> | null = null

async function refreshAccessToken(): Promise<string | null> {
  if (refreshInFlight) return refreshInFlight
  refreshInFlight = (async () => {
    const session = readSession()
    if (!session) return null
    const response = await fetch('/api/auth/refresh', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: session.refresh_token }),
    })
    const payload = await readResponse(response)
    if (!response.ok) {
      if (response.status === 401) {
        announceExpiredSession()
        return null
      }
      throw new ApiError(errorMessage(payload, response.status), response.status)
    }
    if (
      typeof payload !== 'object' ||
      payload === null ||
      !('access_token' in payload) ||
      !('refresh_token' in payload) ||
      typeof payload.access_token !== 'string' ||
      typeof payload.refresh_token !== 'string'
    ) {
      throw new ApiError('Máy chủ trả về phiên đăng nhập không hợp lệ.', response.status)
    }
    saveSession({
      access_token: payload.access_token,
      refresh_token: payload.refresh_token,
    })
    return payload.access_token
  })()
  try {
    return await refreshInFlight
  } finally {
    refreshInFlight = null
  }
}

export async function apiRequest<T>(
  path: string,
  init: RequestInit = {},
  authenticated = true,
): Promise<T> {
  const session = authenticated ? readSession() : null
  const headers = new Headers(init.headers)
  if (init.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  if (session?.access_token) {
    headers.set('Authorization', `Bearer ${session.access_token}`)
  }

  let response = await fetch(`/api${path}`, { ...init, headers })
  let retriedAfterRefresh = false
  if (response.status === 401 && authenticated && session) {
    const newAccessToken = await refreshAccessToken()
    if (newAccessToken) {
      const retryHeaders = new Headers(headers)
      retryHeaders.set('Authorization', `Bearer ${newAccessToken}`)
      response = await fetch(`/api${path}`, { ...init, headers: retryHeaders })
      retriedAfterRefresh = true
    }
  }

  const payload = await readResponse(response)
  if (!response.ok) {
    if (response.status === 401 && authenticated && (!session || retriedAfterRefresh)) {
      announceExpiredSession()
    }
    throw new ApiError(errorMessage(payload, response.status), response.status)
  }
  return payload as T
}
```

FE/src/services/authService.ts
```
import type {
  LoginRequest,
  LoginResponse,
  RegisterRequest,
  User,
} from '../models/auth'
import { apiRequest, saveSession } from './apiClient'

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function isUser(value: unknown): value is User {
  if (!isRecord(value)) {
    return false
  }

  return (
    typeof value.id === 'number' &&
    typeof value.username === 'string' &&
    typeof value.email === 'string'
  )
}

function isLoginResponse(value: unknown): value is LoginResponse {
  if (!isRecord(value)) {
    return false
  }

  return (
    typeof value.message === 'string' &&
    typeof value.access_token === 'string' &&
    typeof value.refresh_token === 'string' &&
    typeof value.expires_in === 'number' &&
    typeof value.token_type === 'string' &&
    isUser(value.user)
  )
}

export async function login(data: LoginRequest): Promise<LoginResponse> {
  const payload: unknown = await apiRequest(
    '/auth/login',
    { method: 'POST', body: JSON.stringify(data) },
    false,
  )

  if (!isLoginResponse(payload)) {
    throw new Error('Máy chủ trả về dữ liệu đăng nhập không hợp lệ.')
  }

  saveSession(payload)
  return payload
}

export async function register(data: RegisterRequest): Promise<User> {
  const payload: unknown = await apiRequest(
    '/auth/register',
    { method: 'POST', body: JSON.stringify(data) },
    false,
  )

  if (!isUser(payload)) {
    throw new Error('Máy chủ trả về dữ liệu đăng ký không hợp lệ.')
  }

  return payload
}
```

FE/src/services/contentService.ts
```
import type {
  AlgorithmDetail,
  AlgorithmSummary,
  Category,
  Comment,
  HomeData,
  LearningProgress,
  Page,
  Rating,
  UserProfile,
} from '../models/api'
import { apiRequest } from './apiClient'

type ListOptions = {
  page?: number
  pageSize?: number
  categoryId?: number
  difficulty?: AlgorithmSummary['difficulty']
  sort?: 'name' | 'rating' | 'newest'
}

function queryString(values: Record<string, string | number | undefined>): string {
  const query = new URLSearchParams()
  Object.entries(values).forEach(([key, value]) => {
    if (value !== undefined) query.set(key, String(value))
  })
  const serialized = query.toString()
  return serialized ? `?${serialized}` : ''
}

export const getMe = () => apiRequest<UserProfile>('/users/me')
export const getHome = () => apiRequest<HomeData>('/home')
export const getCategories = () => apiRequest<Category[]>('/categories')
export const getAlgorithm = (slug: string) =>
  apiRequest<AlgorithmDetail>(`/algorithms/${encodeURIComponent(slug)}`)

export function getAlgorithms(options: ListOptions = {}) {
  return apiRequest<Page<AlgorithmSummary>>(
    `/algorithms${queryString({
      page: options.page ?? 1,
      page_size: options.pageSize ?? 20,
      category_id: options.categoryId,
      difficulty: options.difficulty,
      sort: options.sort ?? 'name',
    })}`,
  )
}

export function searchAlgorithms(q: string, page = 1) {
  return apiRequest<Page<AlgorithmSummary & { matched_in: string }>>(
    `/search${queryString({ q, page, page_size: 20 })}`,
  )
}

export function getSuggestions(q: string) {
  return apiRequest<Array<{ slug: string; name: string }>>(
    `/search/suggestions${queryString({ q, limit: 6 })}`,
  )
}

export const getFavorites = (page = 1) =>
  apiRequest<Page<AlgorithmSummary>>(
    `/users/me/favorites${queryString({ page, page_size: 100 })}`,
  )

export const getProgress = (id: number) =>
  apiRequest<LearningProgress>(`/algorithms/${id}/progress`)

export const updateProgress = (
  id: number,
  status: LearningProgress['status'],
  progress_percent: number,
) =>
  apiRequest<LearningProgress>(`/algorithms/${id}/progress`, {
    method: 'PUT',
    body: JSON.stringify({ status, progress_percent }),
  })

export const saveFavorite = (id: number) =>
  apiRequest<{ message: string }>(`/algorithms/${id}/favorite`, { method: 'POST' })

export const removeFavorite = (id: number) =>
  apiRequest<void>(`/algorithms/${id}/favorite`, { method: 'DELETE' })

export const getComments = (id: number) =>
  apiRequest<Page<Comment>>(`/algorithms/${id}/comments?page=1&page_size=20&sort=newest`)

export const addComment = (id: number, content: string) =>
  apiRequest<Comment>(`/algorithms/${id}/comments`, {
    method: 'POST',
    body: JSON.stringify({ content, parent_id: null }),
  })

export const getRating = (id: number) =>
  apiRequest<Rating>(`/algorithms/${id}/rating`)

export const setRating = (id: number, score: number) =>
  apiRequest<Rating>(`/algorithms/${id}/rating`, {
    method: 'PUT',
    body: JSON.stringify({ score }),
  })

export const updateProfile = (full_name: string) =>
  apiRequest<UserProfile>('/users/me', {
    method: 'PATCH',
    body: JSON.stringify({ full_name }),
  })
```

</source_code>