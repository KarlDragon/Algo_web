# Algo_web
// BE
FastAPI framework

SQLAlchemy 2.0 + Alembic

Set `DATABASE_URL` in `BE/.env` to configure the database. SQL statement logging is disabled by default; set `SQLALCHEMY_ECHO=true` to enable it. The FastAPI lifespan creates missing tables with SQLAlchemy `create_all`; it does not update existing schemas, so schema changes must be applied with Alembic migrations.

