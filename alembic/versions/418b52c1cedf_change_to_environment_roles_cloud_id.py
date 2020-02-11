"""change to environment_roles.cloud_Id

Revision ID: 418b52c1cedf
Revises: 542bd3215dec
Create Date: 2020-02-05 13:40:37.870183

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '418b52c1cedf' # pragma: allowlist secret
down_revision = '542bd3215dec' # pragma: allowlist secret
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('environment_roles', sa.Column('cloud_id', sa.String(), nullable=True))
    op.drop_column('environment_roles', 'csp_user_id')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('environment_roles', sa.Column('csp_user_id', sa.VARCHAR(), autoincrement=False, nullable=True))
    op.drop_column('environment_roles', 'cloud_id')
    # ### end Alembic commands ###
