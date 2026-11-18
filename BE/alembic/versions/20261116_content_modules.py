"""Create content, interaction, search and optional learning tables.
Revision ID: 20261116_content_modules
Revises: 20261113_auth_upgrade

SAFE for existing Auth databases. No existing columns are dropped or changed.
"""
from alembic import op
from Models.Base import Base
from Models.Algorithms import (Category,Algorithm,CodeSample,Tag,AlgorithmTag,
                               AlgorithmExample,AlgorithmDiagram,VisualizationConfig,HomeBanner)
from Models.Interaction import Comment,Rating,Favorite,LearningProgress
from Models.Users import User
from Models.AuthToken import RefreshToken,PasswordResetToken

revision='20261116_content_modules'
down_revision='20261113_auth_upgrade'
branch_labels=None
depends_on=None

TABLES=[Category.__table__,Algorithm.__table__,CodeSample.__table__,Tag.__table__,AlgorithmTag.__table__,
        AlgorithmExample.__table__,AlgorithmDiagram.__table__,VisualizationConfig.__table__,HomeBanner.__table__,
        Comment.__table__,Rating.__table__,Favorite.__table__,LearningProgress.__table__]


def upgrade():
    # Allows existing local DBs whose new tables were created by create_all.
    Base.metadata.create_all(bind=op.get_bind(),tables=TABLES,checkfirst=True)


def downgrade():
    # DESTRUCTIVE: only use on disposable test databases.
    Base.metadata.drop_all(bind=op.get_bind(),tables=TABLES,checkfirst=True)
