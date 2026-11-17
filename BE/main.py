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
