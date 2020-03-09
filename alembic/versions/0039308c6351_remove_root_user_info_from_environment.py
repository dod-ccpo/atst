"""Remove root_user_info from Environment

Revision ID: 0039308c6351
Revises: 17da2a475429
Create Date: 2020-02-04 14:37:06.814645

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0039308c6351' # pragma: allowlist secret
down_revision = '17da2a475429' # pragma: allowlist secret
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('environments', 'root_user_info')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('environments', sa.Column('root_user_info', postgresql.JSONB(astext_type=sa.Text()), autoincrement=False, nullable=True))
    # ### end Alembic commands ###