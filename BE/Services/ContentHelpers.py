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
