"""Initial Auth migration: upgrade existing users table without deleting data.

Revision ID: 20261113_auth_upgrade
Revises:
"""
from alembic import op
import sqlalchemy as sa

revision = "20261113_auth_upgrade"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    tables = sa.inspect(bind).get_table_names()
    if "users" not in tables:
        op.create_table(
            "users",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("username", sa.String(50), nullable=False, unique=True),
            sa.Column("hashPassword", sa.String(255), nullable=False),
            sa.Column("email", sa.String(100), nullable=False, unique=True),
            sa.Column("role", sa.String(10), nullable=False, server_default="USER"),
            sa.Column("fullName", sa.String(100), nullable=True),
            sa.Column("avatarUrl", sa.String(500), nullable=True),
            sa.Column("createdAt", sa.DateTime(), nullable=False,
                      server_default=sa.text("CURRENT_TIMESTAMP")),
        )
    else:
        cols = {c["name"] for c in sa.inspect(bind).get_columns("users")}
        # Check BEFORE converting existing addresses to lowercase.
        clash = bind.execute(sa.text(
            "SELECT lower(email), count(*) FROM users GROUP BY lower(email) "
            "HAVING count(*) > 1 LIMIT 1"
        )).first()
        if clash:
            raise RuntimeError(
                "Có email trùng nhau khi bỏ phân biệt hoa/thường. "
                "Hãy xử lý dữ liệu trước khi migration."
            )
        bind.execute(sa.text("UPDATE users SET email = lower(trim(email))"))
        # Add nullable first to avoid SQLite non-constant DEFAULT restriction.
        if "role" not in cols:
            op.add_column("users", sa.Column("role", sa.String(10), nullable=True))
        if "fullName" not in cols:
            op.add_column("users", sa.Column("fullName", sa.String(100), nullable=True))
        if "avatarUrl" not in cols:
            op.add_column("users", sa.Column("avatarUrl", sa.String(500), nullable=True))
        if "createdAt" not in cols:
            op.add_column("users", sa.Column("createdAt", sa.DateTime(), nullable=True))
        bind.execute(sa.text("UPDATE users SET role = 'USER' WHERE role IS NULL"))
        bind.execute(sa.text(
            "UPDATE users SET createdAt = CURRENT_TIMESTAMP WHERE createdAt IS NULL"
        ))
        # Batch mode recreates SQLite table preserving rows and existing UNIQUEs.
        with op.batch_alter_table("users", recreate="always") as batch:
            batch.alter_column("role", existing_type=sa.String(10), nullable=False,
                               server_default="USER")
            batch.alter_column("createdAt", existing_type=sa.DateTime(),
                               nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"))

    # If create_all ran before Alembic, these new tables may already exist.
    existing = set(sa.inspect(bind).get_table_names())
    if "refresh_tokens" not in existing:
        op.create_table(
            "refresh_tokens",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
            sa.Column("family_id", sa.String(36), nullable=False),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("revoked_at", sa.DateTime(), nullable=True),
            sa.Column("replaced_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])
        op.create_index("ix_refresh_tokens_family_id", "refresh_tokens", ["family_id"])
    if "password_reset_tokens" not in existing:
        op.create_table(
            "password_reset_tokens",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("used_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_password_reset_tokens_user_id", "password_reset_tokens", ["user_id"])


def downgrade():
    op.drop_index("ix_password_reset_tokens_user_id", table_name="password_reset_tokens")
    op.drop_table("password_reset_tokens")
    op.drop_index("ix_refresh_tokens_family_id", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_user_id", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")
    with op.batch_alter_table("users", recreate="always") as batch:
        batch.drop_column("createdAt")
        batch.drop_column("avatarUrl")
        batch.drop_column("fullName")
        batch.drop_column("role")
