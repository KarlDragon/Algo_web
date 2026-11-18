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
