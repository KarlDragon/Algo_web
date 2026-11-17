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
