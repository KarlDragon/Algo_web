"""Safeguard: pytest always uses an isolated throwaway SQLite database."""
import os
import sys
import tempfile
from pathlib import Path

import pytest

TEST_DIR=tempfile.TemporaryDirectory(prefix='algoweb-tests-')
os.environ['DATABASE_URL']=f"sqlite:///{Path(TEST_DIR.name, 'test.db').as_posix()}"
os.environ['JWT_SECRET_KEY']='test-only-not-for-deploy-'+'x'*48
os.environ['JWT_ALGORITHM']='HS256'
os.environ['ACCESS_TOKEN_EXPIRE_MINUTES']='30'
# Mask real .env settings, not just remove them: load_dotenv() would otherwise
# repopulate credentials and tests could accidentally deliver real emails.
for key in ('SMTP_HOST','SMTP_USERNAME','SMTP_PASSWORD','SMTP_FROM',
            'FRONTEND_RESET_PASSWORD_URL','REDIS_URL','TRUSTED_HOSTS'):
    os.environ[key]=''
os.environ['FORCE_HTTPS']='false'
os.environ['SQLALCHEMY_ECHO']='false'
os.environ['CORS_ORIGINS']='http://localhost:5173,http://127.0.0.1:5173'
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

@pytest.fixture(scope='session',autouse=True)
def cleanup_sqlite():
    yield
    from database import engine
    engine.dispose()
    TEST_DIR.cleanup()

@pytest.fixture(autouse=True)
def clear_local_rate_limit_between_tests():
    """Avoid in-memory rate-limit state leaking across unrelated test cases."""
    from Services.RateLimiter import auth_rate_limiter
    with auth_rate_limiter._lock:
        auth_rate_limiter._events.clear()
