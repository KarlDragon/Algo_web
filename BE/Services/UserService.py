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
