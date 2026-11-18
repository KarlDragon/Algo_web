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
