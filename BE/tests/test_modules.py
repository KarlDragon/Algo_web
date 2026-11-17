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
