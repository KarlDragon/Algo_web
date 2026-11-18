from typing import Literal
from fastapi import APIRouter,Depends,Query
from sqlalchemy.orm import Session
from database import get_db
from Models.Users import User
from Schemas.ContentSchemas import ProfileInput,RoleInput
from Services.AuthDependencies import get_current_user,require_admin
from Services.ContentHelpers import user_out
from Services.InteractionService import InteractionService
from Services.UserService import UserService
from Schemas.ResponseSchemas import UserResponse, UserPage, FavoritePage, HistoryPage

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

@router.get('/me/history',response_model=HistoryPage)
def my_history(page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100),
               status:Literal['IN_PROGRESS','COMPLETED']|None=None,
               user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    return InteractionService(db).history(user.id,page,page_size,status)

@router.get('', response_model=UserPage)
def users(page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100),
          q:str|None=None,role:str|None=Query(None,pattern='^(USER|ADMIN)$'),
          admin:User=Depends(require_admin),db:Session=Depends(get_db)):
    return UserService(db).list_users(page,page_size,q,role)

@router.patch('/{user_id}/role', response_model=UserResponse)
def update_role(user_id:int,data:RoleInput,admin:User=Depends(require_admin),db:Session=Depends(get_db)):
    return UserService(db).change_role(admin,user_id,data.role)
