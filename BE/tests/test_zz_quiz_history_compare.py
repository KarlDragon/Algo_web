import time
from uuid import uuid4

from fastapi.testclient import TestClient

from database import SessionLocal
from main import app
from Models.Users import User


PASSWORD = 'Test@2026'


def new_user(client, label):
    username = f'{label}{uuid4().hex[:10]}'
    email = f'{username}@example.com'
    registered = client.post('/auth/register', json={
        'username': username,
        'email': email,
        'password': PASSWORD,
    })
    assert registered.status_code == 201, registered.text
    login = client.post('/auth/login', json={
        'login': username,
        'password': PASSWORD,
    })
    assert login.status_code == 200, login.text
    return {'Authorization': f"Bearer {login.json()['access_token']}"}, registered.json()['id'], username


def promote_to_admin(client, headers, user_id, username):
    with SessionLocal() as db:
        db.get(User, user_id).role = 'ADMIN'
        db.commit()
    login = client.post('/auth/login', json={
        'login': username,
        'password': PASSWORD,
    })
    assert login.status_code == 200, login.text
    return {'Authorization': f"Bearer {login.json()['access_token']}"}


def new_algorithm(client, admin, category_id, slug):
    response = client.post('/algorithms', headers=admin, json={
        'slug': slug,
        'category_id': category_id,
        'difficulty': 'EASY',
        'name': f'Thuật toán {slug}',
        'summary': 'Thuật toán dùng trong kiểm thử lịch sử và so sánh.',
        'theory': 'Mô tả lý thuyết.',
        'pseudocode': 'return input',
        'complexity': {
            'time_best': 'O(n)',
            'time_average': 'O(n log n)',
            'time_worst': 'O(n²)',
            'space': 'O(1)',
        },
        'has_simulation': True,
        'tags': ['Kiểm thử'],
    })
    assert response.status_code == 201, response.text
    return response.json()


def new_category(client, admin, slug):
    response = client.post('/categories', headers=admin, json={
        'name': 'Danh mục kiểm thử',
        'slug': slug,
    })
    assert response.status_code == 201, response.text
    return response.json()['id']


def test_history_touches_without_changing_progress_and_filters_soft_deleted():
    with TestClient(app) as client:
        admin_headers, admin_id, admin_username = new_user(client, 'historyadmin')
        admin = promote_to_admin(client, admin_headers, admin_id, admin_username)
        suffix = uuid4().hex[:10]
        category_id = new_category(client, admin, f'history-{suffix}')
        first = new_algorithm(client, admin, category_id, f'history-a-{suffix}')
        second = new_algorithm(client, admin, category_id, f'history-b-{suffix}')
        learner, _, _ = new_user(client, 'historylearner')

        assert client.get('/users/me/history').status_code == 401
        assert client.post(f"/algorithms/{first['id']}/view").status_code == 401

        first_view = client.post(f"/algorithms/{first['id']}/view", headers=learner)
        assert first_view.status_code == 200, first_view.text
        assert first_view.json()['status'] == 'IN_PROGRESS'
        assert first_view.json()['progress_percent'] == 10
        first_timestamp = first_view.json()['last_viewed_at']

        time.sleep(0.002)
        revisited = client.post(f"/algorithms/{first['id']}/view", headers=learner)
        assert revisited.status_code == 200, revisited.text
        assert revisited.json()['last_viewed_at'] > first_timestamp

        completed = client.put(
            f"/algorithms/{first['id']}/progress",
            headers=learner,
            json={'status': 'COMPLETED', 'progress_percent': 100},
        )
        assert completed.status_code == 200, completed.text
        completed_at = completed.json()['completed_at']
        completed_progress = completed.json()['progress_percent']
        time.sleep(0.002)
        touched_completed = client.post(f"/algorithms/{first['id']}/view", headers=learner)
        assert touched_completed.status_code == 200, touched_completed.text
        assert touched_completed.json()['status'] == 'COMPLETED'
        assert touched_completed.json()['progress_percent'] == completed_progress
        assert touched_completed.json()['completed_at'] == completed_at

        assert client.post(f"/algorithms/{second['id']}/view", headers=learner).status_code == 200
        history = client.get('/users/me/history', headers=learner)
        assert history.status_code == 200, history.text
        assert [row['algorithm']['id'] for row in history.json()['data']] == [
            second['id'], first['id'],
        ]
        completed_history = client.get(
            '/users/me/history', headers=learner, params={'status': 'COMPLETED'},
        ).json()['data']
        assert [row['algorithm']['id'] for row in completed_history] == [first['id']]
        active_history = client.get(
            '/users/me/history', headers=learner, params={'status': 'IN_PROGRESS'},
        ).json()['data']
        assert [row['algorithm']['id'] for row in active_history] == [second['id']]
        assert client.get(
            '/users/me/history', headers=learner, params={'status': 'INVALID'},
        ).status_code == 400

        deleted = client.delete(f"/algorithms/{first['id']}", headers=admin)
        assert deleted.status_code == 204, deleted.text
        visible_history = client.get('/users/me/history', headers=learner).json()['data']
        assert [row['algorithm']['id'] for row in visible_history] == [second['id']]


def test_compare_accepts_ids_and_slugs_preserves_order_and_validates():
    with TestClient(app) as client:
        suffix = uuid4().hex[:10]
        headers, user_id, username = new_user(client, 'compareadmin')
        admin = promote_to_admin(client, headers, user_id, username)
        category_id = new_category(client, admin, f'compare-{suffix}')
        algorithms = [
            new_algorithm(client, admin, category_id, f'compare-{suffix}-{letter}')
            for letter in 'abcde'
        ]

        by_ids = client.get('/algorithms/compare', headers=admin, params={
            'ids': f"{algorithms[2]['id']},{algorithms[0]['id']}",
        })
        assert by_ids.status_code == 200, by_ids.text
        assert [item['id'] for item in by_ids.json()['algorithms']] == [
            algorithms[2]['id'], algorithms[0]['id'],
        ]
        item = by_ids.json()['algorithms'][0]
        assert item['complexity']['time_best'] == 'O(n)'
        assert item['tags'][0]['name'] == 'Kiểm thử'
        assert 'theory' not in item and 'code_samples' not in item

        by_slugs = client.get('/algorithms/compare', headers=admin, params={
            'ids': f"{algorithms[1]['slug']},{algorithms[3]['slug']}",
        })
        assert by_slugs.status_code == 200, by_slugs.text
        assert [item['slug'] for item in by_slugs.json()['algorithms']] == [
            algorithms[1]['slug'], algorithms[3]['slug'],
        ]
        duplicate = client.get('/algorithms/compare', headers=admin, params={
            'ids': f"{algorithms[0]['slug']},,{algorithms[0]['slug']},{algorithms[1]['slug']}",
        })
        assert duplicate.status_code == 200, duplicate.text
        assert [item['slug'] for item in duplicate.json()['algorithms']] == [
            algorithms[0]['slug'], algorithms[1]['slug'],
        ]
        assert client.get('/algorithms/compare', headers=admin, params={
            'ids': algorithms[0]['slug'],
        }).status_code == 400
        assert client.get('/algorithms/compare', headers=admin, params={
            'ids': ','.join(algorithm['slug'] for algorithm in algorithms),
        }).status_code == 400
        missing = client.get('/algorithms/compare', headers=admin, params={
            'ids': f"{algorithms[0]['slug']},no-such-algorithm",
        })
        assert missing.status_code == 404
        assert 'no-such-algorithm' in missing.json()['detail']
        assert client.get('/algorithms/compare', params={
            'ids': f"{algorithms[0]['slug']},{algorithms[1]['slug']}",
        }).status_code == 401


def test_reserved_category_slugs_are_rejected_on_create_and_update():
    with TestClient(app) as client:
        headers, user_id, username = new_user(client, 'slugadmin')
        admin = promote_to_admin(client, headers, user_id, username)

        created = client.post('/categories', headers=admin, json={
            'name': 'Lịch sử', 'slug': 'history',
        })
        assert created.status_code == 400, created.text
        category_id = new_category(client, admin, f'custom-{uuid4().hex[:10]}')
        updated = client.put(f'/categories/{category_id}', headers=admin, json={
            'name': 'Danh mục đổi tên', 'slug': 'compare',
        })
        assert updated.status_code == 400, updated.text
