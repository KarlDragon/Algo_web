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
